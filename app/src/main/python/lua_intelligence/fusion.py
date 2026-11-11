"""Deterministic multi-candidate fusion for Smart Lua recovery.

This layer never executes recovered code. It only combines already-produced,
parser-validated source candidates using structural evidence and pairwise
semantic agreement. A single weak candidate cannot become SUCCESS merely by
having a high lexical score.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .oracle import differential_validate, parse_source, semantic_signature


@dataclass(frozen=True)
class FusionCandidate:
    engine: str
    path: Path
    note: str = ""


@dataclass(frozen=True)
class FusionDecision:
    selected_engine: str | None
    selected_path: Path | None
    confidence: float
    status: str
    scores: dict[str, float]
    agreement: dict[str, int]
    reasons: tuple[str, ...]


def _similarity(a: Path, b: Path) -> float:
    result = differential_validate(a, b)
    return max(0.0, min(1.0, result.score))


def _candidate_score(path: Path, peers: list[Path]) -> tuple[float, int, list[str]]:
    parser = parse_source(path)
    parser_score = parser.score if parser.ok else min(parser.score, 0.49)
    similarities = [_similarity(path, peer) for peer in peers if peer != path]
    strong = sum(1 for score in similarities if score >= 0.75)
    agreement = (sum(similarities) / len(similarities)) if similarities else 0.0

    # Parser acceptance is necessary but deliberately not sufficient.
    score = 0.55 * parser_score + 0.30 * agreement + 0.15 * min(1.0, strong / 2.0)
    reasons = [
        f"parser={parser_score:.3f}",
        f"peer_agreement={agreement:.3f}",
        f"strong_peers={strong}",
    ]
    return score, strong, reasons


def fuse_candidates(candidates: Iterable[FusionCandidate]) -> FusionDecision:
    items = [c for c in candidates if c.path.is_file() and c.path.stat().st_size > 0]
    if not items:
        return FusionDecision(None, None, 0.0, "FAILED", {}, {}, ("no candidates",))

    # Deterministic ordering makes the decision reproducible across CI/Android.
    items.sort(key=lambda c: (c.engine, str(c.path)))
    paths = [c.path for c in items]
    scores: dict[str, float] = {}
    agreement: dict[str, int] = {}
    reasons: list[str] = []

    for item in items:
        score, strong, why = _candidate_score(item.path, paths)
        scores[item.engine] = round(score, 6)
        agreement[item.engine] = strong
        reasons.append(item.engine + ": " + ", ".join(why))

    ranked = sorted(items, key=lambda c: (-scores[c.engine], c.engine, str(c.path)))
    winner = ranked[0]
    winner_score = scores[winner.engine]

    # No consensus means we retain the best candidate as PARTIAL, never SUCCESS.
    # Two or more candidates must independently agree at semantic level before
    # the fusion layer can issue a high-confidence selection.
    consensus = agreement[winner.engine] >= 1 if len(items) > 1 else False
    if winner_score >= 0.82 and consensus:
        status = "CONSENSUS"
    elif winner_score >= 0.55:
        status = "PARTIAL"
    else:
        status = "FAILED"

    if status == "FAILED":
        return FusionDecision(
            None, None, winner_score, status, scores, agreement,
            tuple(reasons + ["no candidate reached the fusion acceptance floor"]),
        )

    return FusionDecision(
        winner.engine, winner.path, winner_score, status, scores, agreement,
        tuple(reasons),
    )


def semantic_equivalence(a: Path, b: Path) -> bool:
    """Public deterministic semantic-equivalence predicate for regression tests."""
    return _similarity(Path(a), Path(b)) >= 0.75


__all__ = [
    "FusionCandidate",
    "FusionDecision",
    "fuse_candidates",
    "semantic_equivalence",
]
