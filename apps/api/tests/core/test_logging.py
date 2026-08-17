"""JsonFormatter tests — pure logging.Formatter behavior, no app, no
database. See docs/adr/0009-phase-9-production-readiness.md."""

import json
import logging

from app.core.logging import JsonFormatter, request_id_var


def _make_record(
    message: str = "hello", level: int = logging.INFO, **extra: object
) -> logging.LogRecord:
    record = logging.LogRecord(
        name="capacityos.test",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_format_produces_valid_json_with_core_fields() -> None:
    record = _make_record("something happened")
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "something happened"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "capacityos.test"
    assert "timestamp" in payload


def test_format_includes_request_id_when_set() -> None:
    token = request_id_var.set("req-abc-123")
    try:
        payload = json.loads(JsonFormatter().format(_make_record()))
    finally:
        request_id_var.reset(token)
    assert payload["request_id"] == "req-abc-123"


def test_format_omits_request_id_when_not_set() -> None:
    payload = json.loads(JsonFormatter().format(_make_record()))
    assert "request_id" not in payload


def test_format_promotes_extra_fields_into_the_payload() -> None:
    record = _make_record("request completed", status_code=200, duration_ms=12.5)
    payload = json.loads(JsonFormatter().format(record))
    assert payload["status_code"] == 200
    assert payload["duration_ms"] == 12.5


def test_format_includes_exception_text_when_exc_info_present() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logging.LogRecord(
            name="capacityos.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="unexpected error",
            args=(),
            exc_info=sys.exc_info(),
        )
    payload = json.loads(JsonFormatter().format(record))
    assert "ValueError" in payload["exception"]
    assert "boom" in payload["exception"]


def test_format_never_emits_a_field_literally_named_password_or_api_key_by_default() -> None:
    """A structural sanity check, not a content filter: the formatter has no
    special-cased field it always includes — every field it emits was either
    a standard LogRecord attribute or something a caller explicitly passed
    via extra={...}, so the guarantee against logging secrets lives at each
    call site (never pass a secret in `extra`), not in the formatter."""
    payload = json.loads(JsonFormatter().format(_make_record()))
    assert "password" not in payload
    assert "api_key" not in payload
    assert "authorization" not in payload
