"""Pure tests of the Phase 22 snapshot comparison layer — no database, no
FastAPI, no scoring engine involved (same discipline as
tests/domain/test_prioritization.py). Every entry here is a plain dict,
the exact shape PortfolioSnapshot.entries stores (Decimal-as-string,
category-as-string), never a recomputed PriorityScoreResult.
"""

from decimal import Decimal

from app.domain.portfolio_snapshot import SnapshotComparisonStatus, compare_snapshot_entries


def _entry(
    project_id: str = "p1",
    project_name: str = "Website Redesign",
    score: str | None = "400",
    rank: int | None = 1,
    category: str | None = None,
) -> dict[str, object]:
    return {
        "project_id": project_id,
        "project_name": project_name,
        "score": score,
        "rank": rank,
        "missing_criteria": [],
        "breakdown": {},
        "category": category,
    }


def test_project_only_in_to_snapshot_is_entered() -> None:
    items = compare_snapshot_entries([], [_entry()])
    assert len(items) == 1
    assert items[0].status == SnapshotComparisonStatus.ENTERED
    assert items[0].rank_from is None
    assert items[0].rank_to == 1
    assert items[0].project_name == "Website Redesign"


def test_project_only_in_from_snapshot_is_left() -> None:
    items = compare_snapshot_entries([_entry()], [])
    assert len(items) == 1
    assert items[0].status == SnapshotComparisonStatus.LEFT
    assert items[0].rank_from == 1
    assert items[0].rank_to is None


def test_identical_entry_in_both_snapshots_is_unchanged() -> None:
    entry = _entry()
    items = compare_snapshot_entries([entry], [dict(entry)])
    assert items[0].status == SnapshotComparisonStatus.UNCHANGED


def test_rank_change_is_reported_as_changed() -> None:
    from_entry = _entry(rank=3)
    to_entry = _entry(rank=1)
    items = compare_snapshot_entries([from_entry], [to_entry])
    assert items[0].status == SnapshotComparisonStatus.CHANGED
    assert items[0].rank_from == 3
    assert items[0].rank_to == 1


def test_score_change_is_reported_as_changed() -> None:
    from_entry = _entry(score="400")
    to_entry = _entry(score="900")
    items = compare_snapshot_entries([from_entry], [to_entry])
    assert items[0].status == SnapshotComparisonStatus.CHANGED
    assert items[0].score_from == Decimal("400")
    assert items[0].score_to == Decimal("900")


def test_moscow_category_change_is_reported_as_changed() -> None:
    from_entry = _entry(score=None, rank=None, category="could")
    to_entry = _entry(score=None, rank=None, category="must")
    items = compare_snapshot_entries([from_entry], [to_entry])
    assert items[0].status == SnapshotComparisonStatus.CHANGED
    assert items[0].category_from is not None and items[0].category_from.value == "could"
    assert items[0].category_to is not None and items[0].category_to.value == "must"


def test_incomplete_score_in_both_snapshots_with_no_change_is_unchanged() -> None:
    entry = _entry(score=None, rank=None)
    items = compare_snapshot_entries([entry], [dict(entry)])
    assert items[0].status == SnapshotComparisonStatus.UNCHANGED
    assert items[0].score_from is None
    assert items[0].score_to is None


def test_project_name_prefers_the_to_snapshot() -> None:
    from_entry = _entry(project_name="Old Name")
    to_entry = _entry(project_name="New Name")
    items = compare_snapshot_entries([from_entry], [to_entry])
    assert items[0].project_name == "New Name"


def test_project_name_falls_back_to_from_snapshot_when_project_left() -> None:
    from_entry = _entry(project_name="Retired Project")
    items = compare_snapshot_entries([from_entry], [])
    assert items[0].project_name == "Retired Project"


def test_result_ordered_by_rank_to_then_rank_from_unranked_last() -> None:
    entries_from = [_entry(project_id="a", rank=5), _entry(project_id="b", rank=None, score=None)]
    entries_to = [_entry(project_id="a", rank=2), _entry(project_id="b", rank=None, score=None)]
    items = compare_snapshot_entries(entries_from, entries_to)
    assert [item.project_id for item in items] == ["a", "b"]


def test_empty_snapshots_produce_no_items() -> None:
    assert compare_snapshot_entries([], []) == []


def test_disjoint_projects_report_one_entered_and_one_left() -> None:
    items = compare_snapshot_entries([_entry(project_id="a")], [_entry(project_id="b")])
    statuses = {item.project_id: item.status for item in items}
    assert statuses == {"a": SnapshotComparisonStatus.LEFT, "b": SnapshotComparisonStatus.ENTERED}
