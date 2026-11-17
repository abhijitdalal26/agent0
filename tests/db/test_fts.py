from agent0.db.fts import or_tsquery, vector_literal


def test_or_tsquery_is_injection_safe():
    q = or_tsquery("what's the Refund policy? ') | !x & (drop)")
    assert q == "what | the | refund | policy | drop"
    assert or_tsquery("a b") == ""


def test_vector_literal():
    assert vector_literal([1.0, 0.5]) == "[1,0.5]"
