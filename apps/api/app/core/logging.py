"""Structured, stdlib-only application logging (CLAUDE.md §34/Phase 9 spec
§14 — no vendor observability platform, no new dependency: `logging` +
`json` are enough). Every record is emitted as one JSON object per line, so
logs are greppable/parseable without a log-shipping agent.

`request_id_var` is the one piece of cross-cutting state: RequestContextMiddleware
(app/api/middleware.py) sets it once per request, and every log record made
during that request — from a route, a service, or an exception handler —
picks it up automatically via JsonFormatter, without threading a request_id
parameter through every function call.

Never log secrets, tokens, passwords, full AI prompts, or full uploaded
files — see docs/adr/0009-phase-9-production-readiness.md "What logging
deliberately never includes."

CAUTION when passing `extra={...}` at a call site: Python's stdlib logging
module raises KeyError at log time (not at import/lint time) if a key
collides with one of LogRecord's own reserved attribute names — `filename`,
`module`, `name`, `msg`, `args`, `levelname`, `levelno`, `pathname`,
`lineno`, `funcName`, `created`, `msecs`, `process`, `processName`,
`thread`, `threadName`, `exc_info`, `exc_text`, `stack_info`, `taskName`.
Prefer a qualified name instead (e.g. `upload_filename`, not `filename`).
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Attributes stdlib LogRecord always carries — anything else on the record
# came from a caller's `extra={...}` and is deliberately promoted into the
# JSON payload as structured context (e.g. status_code, duration_ms,
# subsystem, provider).
_STANDARD_LOG_RECORD_ATTRS = frozenset(
    logging.LogRecord(
        "", 0, "", 0, "", (), None
    ).__dict__.keys()
) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_var.get()
        if request_id is not None:
            payload["request_id"] = request_id
        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOG_RECORD_ATTRS:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Idempotent — safe to call more than once (e.g. once from main.py's
    lifespan, once from a test fixture) without stacking duplicate handlers.
    Configures the ROOT logger, so every module's `logging.getLogger(__name__)`
    inherits the same JSON formatting with no per-module setup."""
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    # uvicorn's own access log duplicates what RequestContextMiddleware
    # already logs (method/path/status/duration, structured, with a request
    # id) — silencing it avoids two differently-shaped log lines per request.
    logging.getLogger("uvicorn.access").disabled = True
