"""File-level (Level 1) parsing for Phase 6 import/export (CLAUDE.md §39
Phase 6). Pure — stdlib `csv`/`json` only on already-read bytes, no
SQLAlchemy, no FastAPI, no I/O beyond that. Turns raw uploaded/exported
bytes into plain dicts; everything past this module (Level 2+ validation,
identity resolution, diffing) lives in app/domain/import_export_diff.py.

See docs/adr/0006-phase-6-import-export.md for the format/column design.
"""

import csv
import io
import json
from enum import StrEnum
from typing import NamedTuple, cast


class ImportEntityType(StrEnum):
    PERSON = "person"
    TEAM = "team"
    TEAM_MEMBERSHIP = "team_membership"
    PROJECT = "project"
    ALLOCATION = "allocation"
    WORKING_SCHEDULE = "working_schedule"
    AVAILABILITY_EXCEPTION = "availability_exception"


class ImportMode(StrEnum):
    UPSERT = "upsert"
    """Default — create-or-update per each entity's identity rule (see
    import_export_diff.py)."""
    CREATE_ONLY = "create_only"
    """A row that matches an existing record becomes a blocking CONFLICT
    row error instead of an update."""
    UPDATE_ONLY = "update_only"
    """A row that matches nothing becomes a blocking row error instead of
    a create."""


class ExportFormat(StrEnum):
    CSV = "csv"
    JSON = "json"


class ImportErrorCode(StrEnum):
    """Stable, machine-readable error codes — the frontend never parses
    prose to determine an error's type (spec Step 8)."""

    FILE_UNREADABLE = "file_unreadable"
    UNSUPPORTED_FORMAT = "unsupported_format"
    FILE_TOO_LARGE = "file_too_large"
    ROW_LIMIT_EXCEEDED = "row_limit_exceeded"
    DUPLICATE_HEADER = "duplicate_header"
    MISSING_REQUIRED_COLUMN = "missing_required_column"
    FIELD_REQUIRED = "field_required"
    FIELD_TYPE_INVALID = "field_type_invalid"
    FIELD_CONSTRAINT_VIOLATED = "field_constraint_violated"
    INVALID_REFERENCE = "invalid_reference"
    DOMAIN_RULE_VIOLATED = "domain_rule_violated"
    DUPLICATE_IN_FILE = "duplicate_in_file"
    CONFLICT = "conflict"
    NO_MATCH_FOR_UPDATE_ONLY = "no_match_for_update_only"


class ColumnSpec(NamedTuple):
    name: str
    required: bool
    """True: this column's HEADER must be present in the file (Level 1).
    Reference columns that participate in an "either/or" pair (e.g.
    person_id / person_email) are never marked required here — their
    presence is a per-row (Level 2/3) concern, checked during reference
    resolution, not a file-level one."""


ENTITY_COLUMNS: dict[ImportEntityType, list[ColumnSpec]] = {
    ImportEntityType.PERSON: [
        ColumnSpec("id", False),
        ColumnSpec("email", True),
        ColumnSpec("first_name", True),
        ColumnSpec("last_name", True),
        ColumnSpec("display_name", False),
        ColumnSpec("job_title", False),
        ColumnSpec("timezone", False),
        ColumnSpec("employment_status", False),
        ColumnSpec("created_at", False),
        ColumnSpec("updated_at", False),
    ],
    ImportEntityType.TEAM: [
        ColumnSpec("id", False),
        ColumnSpec("name", True),
        ColumnSpec("description", False),
        ColumnSpec("created_at", False),
        ColumnSpec("updated_at", False),
    ],
    ImportEntityType.TEAM_MEMBERSHIP: [
        ColumnSpec("id", False),
        ColumnSpec("person_id", False),
        ColumnSpec("person_email", False),
        ColumnSpec("team_id", False),
        ColumnSpec("team_name", False),
        ColumnSpec("created_at", False),
    ],
    ImportEntityType.PROJECT: [
        ColumnSpec("id", False),
        ColumnSpec("external_id", False),
        ColumnSpec("name", True),
        ColumnSpec("description", False),
        ColumnSpec("status", False),
        ColumnSpec("start_date", False),
        ColumnSpec("end_date", False),
        ColumnSpec("created_at", False),
        ColumnSpec("updated_at", False),
    ],
    ImportEntityType.ALLOCATION: [
        ColumnSpec("id", False),
        ColumnSpec("external_id", False),
        ColumnSpec("person_id", False),
        ColumnSpec("person_email", False),
        ColumnSpec("project_id", False),
        ColumnSpec("project_external_id", False),
        ColumnSpec("start_date", True),
        ColumnSpec("end_date", True),
        ColumnSpec("allocation_hours", True),
        ColumnSpec("allocation_unit", False),
        ColumnSpec("notes", False),
        ColumnSpec("created_at", False),
        ColumnSpec("updated_at", False),
    ],
    ImportEntityType.WORKING_SCHEDULE: [
        ColumnSpec("id", False),
        ColumnSpec("external_id", False),
        ColumnSpec("person_id", False),
        ColumnSpec("person_email", False),
        ColumnSpec("effective_start_date", False),
        ColumnSpec("effective_end_date", False),
        ColumnSpec("entries", True),
        ColumnSpec("created_at", False),
        ColumnSpec("updated_at", False),
    ],
    ImportEntityType.AVAILABILITY_EXCEPTION: [
        ColumnSpec("id", False),
        ColumnSpec("external_id", False),
        ColumnSpec("person_id", False),
        ColumnSpec("person_email", False),
        ColumnSpec("start_date", True),
        ColumnSpec("end_date", True),
        ColumnSpec("availability_type", True),
        ColumnSpec("hours", False),
        ColumnSpec("notes", False),
        ColumnSpec("created_at", False),
        ColumnSpec("updated_at", False),
    ],
}
"""Single source of truth for column/header order — shared verbatim by
import parsing (which headers to expect) and export writing (which
columns/order to emit), so the two can never drift apart."""


class ParseFailure(NamedTuple):
    """A whole-file (Level 1) problem — parsing never proceeded to
    producing rows at all."""

    code: ImportErrorCode
    message: str


def detect_format(filename: str | None, content_type: str | None) -> ExportFormat | None:
    """Infers the upload's format from its filename extension, falling back
    to the multipart content-type. None means unrecognized (caller returns
    UNSUPPORTED_FORMAT)."""
    if filename:
        lower = filename.lower()
        if lower.endswith(".csv"):
            return ExportFormat.CSV
        if lower.endswith(".json"):
            return ExportFormat.JSON
    if content_type:
        if "json" in content_type:
            return ExportFormat.JSON
        if "csv" in content_type:
            return ExportFormat.CSV
    return None


def parse_csv_rows(
    raw_bytes: bytes, entity_type: ImportEntityType
) -> list[dict[str, str]] | ParseFailure:
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return ParseFailure(ImportErrorCode.FILE_UNREADABLE, "File is not valid UTF-8 text.")

    if not text.strip():
        return ParseFailure(ImportErrorCode.FILE_UNREADABLE, "File is empty.")

    reader = csv.DictReader(io.StringIO(text))
    fieldnames = reader.fieldnames
    if not fieldnames:
        return ParseFailure(ImportErrorCode.FILE_UNREADABLE, "File has no header row.")

    if len(fieldnames) != len(set(fieldnames)):
        return ParseFailure(
            ImportErrorCode.DUPLICATE_HEADER,
            "The header row contains the same column name more than once.",
        )

    required = {spec.name for spec in ENTITY_COLUMNS[entity_type] if spec.required}
    missing = required - set(fieldnames)
    if missing:
        return ParseFailure(
            ImportErrorCode.MISSING_REQUIRED_COLUMN,
            f"Missing required column(s): {', '.join(sorted(missing))}.",
        )

    try:
        rows = [dict(row) for row in reader]
    except csv.Error as exc:
        return ParseFailure(ImportErrorCode.FILE_UNREADABLE, f"Malformed CSV: {exc}")

    return rows


def parse_json_rows(
    raw_bytes: bytes, entity_type: ImportEntityType
) -> list[dict[str, object]] | ParseFailure:
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return ParseFailure(ImportErrorCode.FILE_UNREADABLE, "File is not valid UTF-8 text.")

    if not text.strip():
        return ParseFailure(ImportErrorCode.FILE_UNREADABLE, "File is empty.")

    try:
        decoded: object = json.loads(text)
    except json.JSONDecodeError as exc:
        return ParseFailure(ImportErrorCode.FILE_UNREADABLE, f"Malformed JSON: {exc.msg}")

    if not isinstance(decoded, list):
        return ParseFailure(
            ImportErrorCode.FILE_UNREADABLE, "JSON import must be a top-level array of objects."
        )
    items = cast(list[object], decoded)
    if not all(isinstance(item, dict) for item in items):
        return ParseFailure(
            ImportErrorCode.FILE_UNREADABLE, "Every array element must be a JSON object."
        )
    rows: list[dict[str, object]] = [item for item in items if isinstance(item, dict)]

    required = {spec.name for spec in ENTITY_COLUMNS[entity_type] if spec.required}
    present_keys: set[str] = set()
    for row in rows:
        present_keys.update(row.keys())
    missing = required - present_keys
    if missing and rows:
        return ParseFailure(
            ImportErrorCode.MISSING_REQUIRED_COLUMN,
            f"No row supplies required field(s): {', '.join(sorted(missing))}.",
        )

    return rows


def coerce_optional_str(raw: str | object | None) -> str | None:
    """Blank/whitespace-only CSV cell or JSON null/empty string -> None."""
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def coerce_entries_cell(raw: str) -> list[dict[str, str]]:
    """Parses WorkingSchedule's packed CSV cell
    'weekday:hours,weekday:hours,...' (e.g. '0:8.00,1:8.00') into the
    list-of-dicts shape WorkingScheduleEntryCreate expects. Raises ValueError
    on malformed input — the caller (normalize_working_schedule_row) turns
    that into a FIELD_TYPE_INVALID row error. JSON rows carry entries as a
    native array already and never call this."""
    entries: list[dict[str, str]] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        weekday_str, sep, hours_str = chunk.partition(":")
        if not sep:
            raise ValueError(f"'{chunk}' is not in 'weekday:hours' format")
        entries.append({"weekday": weekday_str.strip(), "hours": hours_str.strip()})
    if not entries:
        raise ValueError("entries cell is empty")
    return entries


_TEMPLATE_EXAMPLES: dict[ImportEntityType, dict[str, str]] = {
    ImportEntityType.PERSON: {
        "email": "jane.doe@example.com",
        "first_name": "Jane",
        "last_name": "Doe",
        "display_name": "Jane Doe",
        "job_title": "Product Designer",
        "timezone": "UTC",
        "employment_status": "active",
    },
    ImportEntityType.TEAM: {"name": "Design", "description": "Product design team"},
    ImportEntityType.TEAM_MEMBERSHIP: {
        "person_email": "jane.doe@example.com",
        "team_name": "Design",
    },
    ImportEntityType.PROJECT: {
        "external_id": "PRJ-100",
        "name": "Website Redesign",
        "description": "Q4 marketing site refresh",
        "status": "active",
        "start_date": "2026-09-01",
        "end_date": "2026-12-19",
    },
    ImportEntityType.ALLOCATION: {
        "external_id": "ALLOC-100",
        "person_email": "jane.doe@example.com",
        "project_external_id": "PRJ-100",
        "start_date": "2026-09-01",
        "end_date": "2026-09-30",
        "allocation_hours": "40",
        "allocation_unit": "total_hours",
        "notes": "Design phase",
    },
    ImportEntityType.WORKING_SCHEDULE: {
        "external_id": "WS-100",
        "person_email": "jane.doe@example.com",
        "effective_start_date": "2026-09-01",
        "entries": "0:8.00,1:8.00,2:8.00,3:8.00,4:8.00",
    },
    ImportEntityType.AVAILABILITY_EXCEPTION: {
        "external_id": "AVAIL-100",
        "person_email": "jane.doe@example.com",
        "start_date": "2026-09-14",
        "end_date": "2026-09-18",
        "availability_type": "annual_leave",
        "notes": "Summer holiday",
    },
}
"""One realistic, schema-valid example row per entity for build_template.
Keys are a SUBSET of that entity's ENTITY_COLUMNS — build_template fills any
column not listed here with an empty cell, exactly like a user leaving an
optional field blank."""


def build_template(entity_type: ImportEntityType, fmt: ExportFormat) -> bytes:
    """A downloadable example file per entity (spec Step 13): the file's
    real header/column set (ENTITY_COLUMNS, the same source import parsing
    and export both use) plus one realistic, schema-valid example row. Pure
    and DB-free — every value here is a literal, not looked up — so it's
    safe to expose with no repository/service dependency, unlike validate/
    apply/export which all need one."""
    example = _TEMPLATE_EXAMPLES[entity_type]
    if fmt == ExportFormat.JSON:
        row: dict[str, object] = dict(example)
        if entity_type == ImportEntityType.WORKING_SCHEDULE:
            row["entries"] = [
                {"weekday": int(weekday), "hours": hours}
                for weekday, hours in (
                    entry.split(":") for entry in example["entries"].split(",")
                )
            ]
        return json.dumps([row], indent=2).encode("utf-8")

    fieldnames = [spec.name for spec in ENTITY_COLUMNS[entity_type]]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerow({name: example.get(name, "") for name in fieldnames})
    return buffer.getvalue().encode("utf-8")


_INJECTION_TRIGGER_CHARS = ("=", "+", "-", "@")


def sanitize_csv_cell(value: str) -> str:
    """CSV formula-injection defense (OWASP): if the value is non-empty and
    its first character could be interpreted as a formula prefix by Excel/
    Sheets/LibreOffice, prefix a leading apostrophe so it's always read back
    as literal text. Applied to every cell the CSV export writer emits.
    JSON export never calls this — a JSON viewer never executes formulas."""
    if value and value[0] in _INJECTION_TRIGGER_CHARS:
        return f"'{value}"
    return value
