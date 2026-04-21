from __future__ import annotations

from rapidfuzz import fuzz, process

from pyocker_enter.docker_utils import ContainerRecord

_SCORE_CUTOFF = 30


def rank(query: str, containers: list[ContainerRecord]) -> list[ContainerRecord]:
    """Return containers ordered by fuzzy-match score against the query.

    Empty query preserves original order. Non-empty query uses rapidfuzz
    partial_ratio against "{name} {short_id} {image}" and drops records
    scoring below _SCORE_CUTOFF.
    """
    if not query:
        return list(containers)

    haystack = {i: f"{c.name} {c.short_id} {c.image}" for i, c in enumerate(containers)}
    matches = process.extract(
        query,
        haystack,
        scorer=fuzz.partial_ratio,
        limit=None,
        score_cutoff=_SCORE_CUTOFF,
    )
    return [containers[idx] for _, _, idx in matches]
