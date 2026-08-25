"""Phase 22 — portfolio snapshot diff/trend
(docs/adr/0022-portfolio-snapshot-comparison.md).

Pure, DB-free comparison of two ALREADY-FROZEN PortfolioSnapshot.entries
payloads (Phase 21) — no score, rank, or category is ever recalculated
here. This module never imports calculate_priority_score or any other
piece of the scoring engine: a snapshot's entries are historical facts,
already computed once by Phase 17-18's engine at capture time, and a diff
is nothing more than comparing those frozen facts pairwise. Mirrors the
"no fabricated data, no second engine" discipline every prior
prioritization phase established.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any

from app.models.enums import MoscowCategory


class SnapshotComparisonStatus(StrEnum):
    """Never persisted — computed fresh on every comparison read, the same
    "derive, never cache" discipline every Phase 17-21 result follows."""

    ENTERED = "entered"
    """Present in the `to` snapshot, absent from `from` — e.g. a project
    scored under this framework for the first time between the two
    snapshots."""
    LEFT = "left"
    """Present in `from`, absent from `to` — e.g. its score under this
    framework was deleted, or the project itself was deleted, between the
    two snapshots. Never implies the project no longer exists — only that
    it no longer appears in this framework's ranking."""
    CHANGED = "changed"
    """Present in both, but rank, score, or category differs."""
    UNCHANGED = "unchanged"
    """Present in both with an identical rank, score, and category."""


@dataclass(frozen=True)
class SnapshotComparisonItem:
    project_id: str
    project_name: str
    status: SnapshotComparisonStatus
    rank_from: int | None
    rank_to: int | None
    score_from: Decimal | None
    score_to: Decimal | None
    category_from: MoscowCategory | None
    category_to: MoscowCategory | None


def compare_snapshot_entries(
    from_entries: list[dict[str, Any]], to_entries: list[dict[str, Any]]
) -> list[SnapshotComparisonItem]:
    """One item per project appearing in EITHER snapshot's frozen `entries`
    — a project present in only one side is `entered`/`left`, never
    silently omitted. `project_name` prefers the `to` snapshot's frozen
    name (the more recent of the two facts); a project only in `from`
    (status LEFT) has no `to`-side name to prefer, so falls back to its
    `from`-side name. Ordered by `rank_to` (unranked/absent last), then by
    `rank_from`, matching the live portfolio board's own "incomplete
    scores sort last" convention rather than an arbitrary insertion order.
    """
    from_by_id = {entry["project_id"]: entry for entry in from_entries}
    to_by_id = {entry["project_id"]: entry for entry in to_entries}
    project_ids = list(dict.fromkeys([*from_by_id.keys(), *to_by_id.keys()]))

    items: list[SnapshotComparisonItem] = []
    for project_id in project_ids:
        from_entry = from_by_id.get(project_id)
        to_entry = to_by_id.get(project_id)

        rank_from = from_entry["rank"] if from_entry is not None else None
        rank_to = to_entry["rank"] if to_entry is not None else None
        score_from = _to_decimal(from_entry["score"]) if from_entry is not None else None
        score_to = _to_decimal(to_entry["score"]) if to_entry is not None else None
        category_from = _to_category(from_entry["category"]) if from_entry is not None else None
        category_to = _to_category(to_entry["category"]) if to_entry is not None else None

        if from_entry is None:
            status = SnapshotComparisonStatus.ENTERED
            project_name = to_entry["project_name"] if to_entry is not None else ""
        elif to_entry is None:
            status = SnapshotComparisonStatus.LEFT
            project_name = from_entry["project_name"]
        elif (rank_from, score_from, category_from) == (rank_to, score_to, category_to):
            status = SnapshotComparisonStatus.UNCHANGED
            project_name = to_entry["project_name"]
        else:
            status = SnapshotComparisonStatus.CHANGED
            project_name = to_entry["project_name"]

        items.append(
            SnapshotComparisonItem(
                project_id=project_id,
                project_name=project_name,
                status=status,
                rank_from=rank_from,
                rank_to=rank_to,
                score_from=score_from,
                score_to=score_to,
                category_from=category_from,
                category_to=category_to,
            )
        )

    items.sort(
        key=lambda item: (
            item.rank_to is None,
            item.rank_to or 0,
            item.rank_from is None,
            item.rank_from or 0,
        )
    )
    return items


def _to_decimal(value: object) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def _to_category(value: object) -> MoscowCategory | None:
    return MoscowCategory(value) if value is not None else None
