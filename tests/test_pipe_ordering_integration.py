from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web" / "src"


def read(relative: str) -> str:
    return (WEB / relative).read_text(encoding="utf-8")


def test_natural_pipe_order_is_numeric_and_non_mutating() -> None:
    source = read("pipeOrdering.ts")
    assert "numeric: true" in source
    assert ".trim()" in source
    assert ".sort(comparePipeIdentifiers)" in source
    assert "values.map" in source


def test_new_and_edited_logs_are_sorted_before_submission() -> None:
    new_test = read("components/NewTestModal.tsx")
    detail = read("components/TestDetailModal.tsx")
    assert "const sortedPipes = sortPipeInput(pipeRaw)" in new_test
    assert "sortedPipes.join('\\n')" in new_test
    assert "const pipeList = sortPipeInput(editPipes)" in detail
    assert "sortPipeIdentifiers(Array.from(new Set(extractedBundles)))" in detail


def test_existing_logs_are_sorted_at_every_primary_display() -> None:
    for relative in (
        "components/TestCard.tsx",
        "components/TestDetailModal.tsx",
        "components/PublicLogView.tsx",
        "components/TestTableView.tsx",
        "components/NewRecordModal.tsx",
    ):
        assert "sortPipeIdentifiers" in read(relative), relative
