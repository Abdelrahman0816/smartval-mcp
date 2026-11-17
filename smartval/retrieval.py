"""Small dependency-free BM25 retriever over the product catalogue.

This is the "retrieval" step of the RAG flow: the agent asks a question,
the MCP tool calls the REST API, and the API ranks products with BM25 so the
LLM only gets the most relevant product data as context.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from typing import Any

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase, strip accents (å/ä/ö -> a/a/o) and split into word tokens."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return _TOKEN_RE.findall(text)


def product_to_text(product: dict[str, Any]) -> str:
    """Flatten a product (including its specs) into one searchable string."""
    specs = " ".join(f"{k} {v}" for k, v in product.get("specs", {}).items())
    return " ".join(
        str(product.get(field, ""))
        for field in ("name", "brand", "category", "description")
    ) + " " + specs


class BM25Index:
    def __init__(self, products: list[dict[str, Any]], k1: float = 1.5, b: float = 0.75):
        self.products = products
        self.k1 = k1
        self.b = b
        self.docs = [tokenize(product_to_text(p)) for p in products]
        self.doc_freqs = [Counter(d) for d in self.docs]
        self.avgdl = sum(len(d) for d in self.docs) / max(len(self.docs), 1)
        df: Counter[str] = Counter()
        for d in self.docs:
            df.update(set(d))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def score(self, query: str, i: int) -> float:
        freqs = self.doc_freqs[i]
        dl = len(self.docs[i])
        total = 0.0
        for term in tokenize(query):
            if term not in freqs:
                continue
            tf = freqs[term]
            denom = tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
            total += self.idf[term] * tf * (self.k1 + 1) / denom
        return total

    def search(self, query: str, limit: int = 5) -> list[tuple[dict[str, Any], float]]:
        scored = [(p, self.score(query, i)) for i, p in enumerate(self.products)]
        scored = [s for s in scored if s[1] > 0]
        scored.sort(key=lambda s: s[1], reverse=True)
        return scored[:limit]
