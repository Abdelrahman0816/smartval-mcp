def test_health(api):
    r = api.get("/health")
    assert r.status_code == 200
    assert r.json()["products"] > 0


def test_filter_and_sort(api):
    r = api.get("/products", params={"category": "laptop", "max_price": 10000})
    prices = [p["price_sek"] for p in r.json()]
    assert prices and all(p <= 10000 for p in prices)
    assert prices == sorted(prices)


def test_get_product_404(api):
    assert api.get("/products/does-not-exist").status_code == 404


def test_search_ranks_relevant_first(api):
    hits = api.get("/search", params={"q": "brusreducering hörlurar"}).json()
    assert hits[0]["product"]["category"] == "headphones"


def test_search_price_filter(api):
    hits = api.get("/search", params={"q": "laptop", "max_price": 9000}).json()
    assert hits and all(h["product"]["price_sek"] <= 9000 for h in hits)


def test_compare(api):
    body = api.get("/compare", params={"ids": "lap-001,lap-002"}).json()
    assert body["cheapest"] == "lap-001"
    assert body["highest_rated"] == "lap-002"
    assert set(body["spec_table"]["ram_gb"]) == {"lap-001", "lap-002"}


def test_compare_needs_two(api):
    assert api.get("/compare", params={"ids": "lap-001"}).status_code == 422
