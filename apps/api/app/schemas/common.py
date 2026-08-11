from pydantic import BaseModel


class Page[T](BaseModel):
    """List-response envelope.

    Used instead of a bare array so pagination fields (page, page_size,
    next_cursor, ...) can be added later without changing the response
    shape for existing clients.
    """

    items: list[T]
    total: int
