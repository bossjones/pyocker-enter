from __future__ import annotations

from pyocker_enter.fuzzy import rank


def test_empty_query_returns_all_containers_in_original_order(fake_records) -> None:
    assert rank("", fake_records) == fake_records


def test_matching_query_ranks_matches_first(fake_records) -> None:
    """Query 'web' should rank the two web-* containers above 'cache'."""
    result = rank("web", fake_records)
    names = [r.name for r in result]
    # The two web-* records should appear, cache should be dropped by cutoff or ranked last
    assert "web-api" in names
    assert "web-db" in names
    # Matches ordered before non-matches
    non_web = [n for n in names if "web" not in n]
    web = [n for n in names if "web" in n]
    assert names[: len(web)] == web
    assert all(n not in names[: len(web)] for n in non_web)


def test_short_id_matches(fake_records) -> None:
    """A 12-char short_id should resolve uniquely via fuzzy rank."""
    target_short_id = fake_records[1].short_id  # "bbbbbbbbbbbb"
    result = rank(target_short_id, fake_records)
    assert result[0].short_id == target_short_id


def test_low_score_matches_filtered_out(fake_records) -> None:
    """Completely unrelated query returns an empty list (below cutoff)."""
    result = rank("zzzqqqyyy", fake_records)
    # Either empty or doesn't include any of our records by name
    assert all(r.name not in {"web-api", "web-db", "cache"} or False for r in result) or result == []
