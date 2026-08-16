"""Pure tests of Level-1 (file) parsing — no database, no FastAPI (same
discipline as tests/domain/test_capacity.py)."""

import pytest

from app.domain.import_export_parsing import (
    ExportFormat,
    ImportEntityType,
    ImportErrorCode,
    ParseFailure,
    coerce_entries_cell,
    coerce_optional_str,
    detect_format,
    parse_csv_rows,
    parse_json_rows,
    sanitize_csv_cell,
)

# ---------------------------------------------------------------------------
# detect_format
# ---------------------------------------------------------------------------


def test_detect_format_from_filename_extension() -> None:
    assert detect_format("people.csv", None) == ExportFormat.CSV
    assert detect_format("people.json", None) == ExportFormat.JSON


def test_detect_format_falls_back_to_content_type() -> None:
    assert detect_format(None, "application/json") == ExportFormat.JSON
    assert detect_format(None, "text/csv") == ExportFormat.CSV


def test_detect_format_returns_none_when_unrecognized() -> None:
    assert detect_format("people.xlsx", "application/vnd.ms-excel") is None
    assert detect_format(None, None) is None


# ---------------------------------------------------------------------------
# parse_csv_rows
# ---------------------------------------------------------------------------


def test_parse_csv_rows_valid() -> None:
    raw = b"email,first_name,last_name\njane@example.com,Jane,Doe\n"
    result = parse_csv_rows(raw, ImportEntityType.PERSON)
    assert result == [{"email": "jane@example.com", "first_name": "Jane", "last_name": "Doe"}]


def test_parse_csv_rows_empty_file() -> None:
    result = parse_csv_rows(b"", ImportEntityType.PERSON)
    assert isinstance(result, ParseFailure)
    assert result.code == ImportErrorCode.FILE_UNREADABLE


def test_parse_csv_rows_invalid_encoding() -> None:
    result = parse_csv_rows(b"\xff\xfe\x00\x01", ImportEntityType.PERSON)
    assert isinstance(result, ParseFailure)
    assert result.code == ImportErrorCode.FILE_UNREADABLE


def test_parse_csv_rows_duplicate_header() -> None:
    raw = b"email,email,first_name\njane@example.com,x,Jane\n"
    result = parse_csv_rows(raw, ImportEntityType.PERSON)
    assert isinstance(result, ParseFailure)
    assert result.code == ImportErrorCode.DUPLICATE_HEADER


def test_parse_csv_rows_missing_required_header() -> None:
    raw = b"first_name,last_name\nJane,Doe\n"
    result = parse_csv_rows(raw, ImportEntityType.PERSON)
    assert isinstance(result, ParseFailure)
    assert result.code == ImportErrorCode.MISSING_REQUIRED_COLUMN
    assert "email" in result.message


def test_parse_csv_rows_unexpected_extra_column_is_harmless() -> None:
    raw = b"email,first_name,last_name,favorite_color\nj@x.com,Jane,Doe,blue\n"
    result = parse_csv_rows(raw, ImportEntityType.PERSON)
    assert not isinstance(result, ParseFailure)
    assert result[0]["favorite_color"] == "blue"


# ---------------------------------------------------------------------------
# parse_json_rows
# ---------------------------------------------------------------------------


def test_parse_json_rows_valid() -> None:
    raw = b'[{"email": "jane@example.com", "first_name": "Jane", "last_name": "Doe"}]'
    result = parse_json_rows(raw, ImportEntityType.PERSON)
    assert result == [{"email": "jane@example.com", "first_name": "Jane", "last_name": "Doe"}]


def test_parse_json_rows_malformed() -> None:
    result = parse_json_rows(b"{not valid json", ImportEntityType.PERSON)
    assert isinstance(result, ParseFailure)
    assert result.code == ImportErrorCode.FILE_UNREADABLE


def test_parse_json_rows_not_an_array() -> None:
    result = parse_json_rows(b'{"email": "jane@example.com"}', ImportEntityType.PERSON)
    assert isinstance(result, ParseFailure)
    assert result.code == ImportErrorCode.FILE_UNREADABLE


def test_parse_json_rows_array_element_not_object() -> None:
    result = parse_json_rows(b'["not-an-object"]', ImportEntityType.PERSON)
    assert isinstance(result, ParseFailure)
    assert result.code == ImportErrorCode.FILE_UNREADABLE


def test_parse_json_rows_empty_array_is_valid_zero_rows() -> None:
    result = parse_json_rows(b"[]", ImportEntityType.PERSON)
    assert result == []


# ---------------------------------------------------------------------------
# coerce_optional_str
# ---------------------------------------------------------------------------


def test_coerce_optional_str_blank_becomes_none() -> None:
    assert coerce_optional_str("") is None
    assert coerce_optional_str("   ") is None
    assert coerce_optional_str(None) is None


def test_coerce_optional_str_preserves_value() -> None:
    assert coerce_optional_str(" Jane ") == "Jane"


# ---------------------------------------------------------------------------
# coerce_entries_cell
# ---------------------------------------------------------------------------


def test_coerce_entries_cell_parses_packed_format() -> None:
    result = coerce_entries_cell("0:8.00,1:8.00,2:8.00")
    assert result == [
        {"weekday": "0", "hours": "8.00"},
        {"weekday": "1", "hours": "8.00"},
        {"weekday": "2", "hours": "8.00"},
    ]


def test_coerce_entries_cell_rejects_malformed_chunk() -> None:
    with pytest.raises(ValueError, match="weekday:hours"):
        coerce_entries_cell("0-8.00")


def test_coerce_entries_cell_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        coerce_entries_cell("")


# ---------------------------------------------------------------------------
# sanitize_csv_cell
# ---------------------------------------------------------------------------


def test_sanitize_csv_cell_prefixes_all_four_trigger_characters() -> None:
    assert sanitize_csv_cell("=1+1") == "'=1+1"
    assert sanitize_csv_cell("+1") == "'+1"
    assert sanitize_csv_cell("-1") == "'-1"
    assert sanitize_csv_cell("@SUM(A1)") == "'@SUM(A1)"


def test_sanitize_csv_cell_leaves_normal_values_unchanged() -> None:
    assert sanitize_csv_cell("Jane Doe") == "Jane Doe"
    assert sanitize_csv_cell("") == ""
    assert sanitize_csv_cell("40.00") == "40.00"
