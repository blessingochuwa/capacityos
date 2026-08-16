"""Pydantic contracts for Phase 6 import/export (CLAUDE.md §39 Phase 6).

Signal type/severity vocabulary lives in app/domain/import_export_parsing.py
(ImportEntityType, ImportMode, ExportFormat, ImportErrorCode) since parsing
needs them directly; this module builds the request/response report shapes
on top of them. See docs/adr/0006-phase-6-import-export.md.
"""

import uuid
from enum import StrEnum

from pydantic import BaseModel

from app.domain.import_export_parsing import ImportEntityType, ImportErrorCode, ImportMode

__all__ = [
    "ImportApplyResult",
    "ImportEntityType",
    "ImportErrorCode",
    "ImportFieldError",
    "ImportMode",
    "ImportRowResult",
    "ImportRowStatus",
    "ImportValidationReport",
]


class ImportRowStatus(StrEnum):
    VALID_CREATE = "valid_create"
    VALID_UPDATE = "valid_update"
    VALID_UNCHANGED = "valid_unchanged"
    INVALID = "invalid"


class ImportFieldError(BaseModel):
    field: str | None
    """None for a row-level error not specific to one column (e.g. an
    unresolvable reference spanning two columns, or a whole-row conflict)."""
    code: ImportErrorCode
    message: str


class ImportRowResult(BaseModel):
    row_number: int
    """1-based, header row excluded — row 1 is the first data row."""
    status: ImportRowStatus
    identity: str | None
    """The identity used to match this row, e.g. "email=jane@x.com" or
    "external_id=PRJ-100". None when the entity has no natural key and the
    row would always create (see docs/adr/0006-phase-6-import-export.md)."""
    matched_id: uuid.UUID | None
    """The existing record's id this row matched, if any (status
    valid_update/valid_unchanged only)."""
    errors: list[ImportFieldError]


class ImportValidationReport(BaseModel):
    entity_type: ImportEntityType
    mode: ImportMode
    file_error: ImportFieldError | None = None
    """A whole-file (Level 1) problem — parsing never reached individual
    rows at all. When set, total_rows is 0, rows is empty, and
    ready_to_apply is False."""
    total_rows: int
    valid_create_count: int
    valid_update_count: int
    valid_unchanged_count: int
    invalid_count: int
    ready_to_apply: bool
    """True iff file_error is None, invalid_count == 0, and total_rows > 0."""
    rows: list[ImportRowResult]


class ImportApplyResult(BaseModel):
    entity_type: ImportEntityType
    mode: ImportMode
    file_error: ImportFieldError | None = None
    applied: bool
    """False whenever anything failed — nothing was written (all-or-nothing,
    see docs/adr/0006-phase-6-import-export.md)."""
    total_rows: int
    created_count: int
    updated_count: int
    unchanged_count: int
    invalid_count: int
    rows: list[ImportRowResult]
