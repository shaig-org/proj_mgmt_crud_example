"""Capability layer error types."""


class CapabilityPermissionError(Exception):
    """Raised by capability verbs when an authenticated user is not allowed.

    Mapped to HTTP 403 by a FastAPI exception handler registered in app.py.
    The `detail` is exposed verbatim in the `{"detail": ...}` response envelope.
    """

    def __init__(self, detail: str, *, code: str = "forbidden") -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code


class CapabilityNotFoundError(Exception):
    """Raised by capability factories when the bound entity does not exist.

    Mapped to HTTP 404 by a FastAPI exception handler registered in app.py.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail
