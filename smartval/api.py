"""REST API for the SmartValGuiden product catalogue (FastAPI).

Run locally:  uvicorn smartval.api:app --reload
Docs:         http://localhost:8000/docs
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .retrieval import BM25Index

DEFAULT_DATA = Path(__file__).resolve().parent.parent / "data" / "products.json"


class Product(BaseModel):
    id: str
    name: str
    brand: str
    category: str
    price_sek: int = Field(ge=0)
    rating: float = Field(ge=0, le=5)
    specs: dict[str, Any] = {}
    description: str = ""


class SearchHit(BaseModel):
    product: Product
    score: float


class Comparison(BaseModel):
    products: list[Product]
    cheapest: str
    highest_rated: str
    spec_table: dict[str, dict[str, Any]]


def load_products(path: Path) -> list[Product]:
    """Load and validate product data. Invalid rows or duplicate ids fail fast."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    products = [Product.model_validate(p) for p in raw]
    ids = [p.id for p in products]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f"Duplicate product ids in {path}: {sorted(duplicates)}")
    return products


@lru_cache
def catalogue() -> tuple[list[Product], BM25Index]:
    products = load_products(Path(os.environ.get("SMARTVAL_DATA", DEFAULT_DATA)))
    return products, BM25Index([p.model_dump() for p in products])


app = FastAPI(
    title="SmartValGuiden Product API",
    description="Product catalogue, search and comparison for SmartValGuiden.se",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, Any]:
    products, _ = catalogue()
    return {"status": "ok", "products": len(products)}


@app.get("/categories")
def categories() -> list[str]:
    products, _ = catalogue()
    return sorted({p.category for p in products})


@app.get("/products", response_model=list[Product])
def list_products(
    category: str | None = None,
    brand: str | None = None,
    min_price: int | None = Query(None, ge=0),
    max_price: int | None = Query(None, ge=0),
    sort: str = Query("price", pattern="^(price|rating|name)$"),
) -> list[Product]:
    products, _ = catalogue()
    result = [
        p for p in products
        if (category is None or p.category.lower() == category.lower())
        and (brand is None or p.brand.lower() == brand.lower())
        and (min_price is None or p.price_sek >= min_price)
        and (max_price is None or p.price_sek <= max_price)
    ]
    if sort == "price":
        result.sort(key=lambda p: p.price_sek)
    elif sort == "rating":
        result.sort(key=lambda p: p.rating, reverse=True)
    else:
        result.sort(key=lambda p: p.name.lower())
    return result


@app.get("/products/{product_id}", response_model=Product)
def get_product(product_id: str) -> Product:
    products, _ = catalogue()
    for p in products:
        if p.id == product_id:
            return p
    raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found")


@app.get("/search", response_model=list[SearchHit])
def search(
    q: str = Query(..., min_length=1, description="Free-text query, Swedish or English"),
    category: str | None = None,
    max_price: int | None = Query(None, ge=0),
    limit: int = Query(5, ge=1, le=20),
) -> list[SearchHit]:
    _, index = catalogue()
    hits = []
    for product, score in index.search(q, limit=len(index.products)):
        if category and product["category"].lower() != category.lower():
            continue
        if max_price is not None and product["price_sek"] > max_price:
            continue
        hits.append(SearchHit(product=Product.model_validate(product), score=round(score, 3)))
    return hits[:limit]


@app.get("/compare", response_model=Comparison)
def compare(ids: str = Query(..., description="Comma-separated product ids, e.g. lap-001,lap-002")) -> Comparison:
    wanted = [i.strip() for i in ids.split(",") if i.strip()]
    if len(wanted) < 2:
        raise HTTPException(status_code=422, detail="Give at least two product ids to compare")
    selected = [get_product(i) for i in wanted]
    spec_keys = sorted({k for p in selected for k in p.specs})
    table = {k: {p.id: p.specs.get(k) for p in selected} for k in ["price_sek", "rating", *spec_keys]}
    for p in selected:
        table["price_sek"][p.id] = p.price_sek
        table["rating"][p.id] = p.rating
    return Comparison(
        products=selected,
        cheapest=min(selected, key=lambda p: p.price_sek).id,
        highest_rated=max(selected, key=lambda p: p.rating).id,
        spec_table=table,
    )
