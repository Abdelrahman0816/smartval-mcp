from smartval.retrieval import BM25Index, tokenize


def test_tokenize_strips_accents():
    assert tokenize("Hörlurar & Skärm!") == ["horlurar", "skarm"]


def test_bm25_prefers_matching_doc():
    idx = BM25Index([
        {"name": "A", "description": "gaming monitor 165hz"},
        {"name": "B", "description": "wireless headphones anc"},
    ])
    assert idx.search("headphones")[0][0]["name"] == "B"
    assert idx.search("nothing-matches") == []
