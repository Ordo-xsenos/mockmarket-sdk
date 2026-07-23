class MockMarketAPIError(Exception):
    def __init__(self, status_code: int, detail: str | None = None) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"[{status_code}] {detail}" if detail else f"[{status_code}]")


class AuthenticationError(MockMarketAPIError):
    def __init__(self, detail: str | None = None) -> None:
        super().__init__(401, detail or "Authentication failed")


class RateLimitError(MockMarketAPIError):
    """429 — too many requests. ``retry_after`` is the server's suggested wait in
    seconds (from the ``Retry-After`` header) when available. Raised only after the
    client's automatic backoff retries are exhausted."""

    def __init__(self, detail: str | None = None, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        super().__init__(429, detail or "Rate limit exceeded")


class NotFoundError(MockMarketAPIError):
    def __init__(self, detail: str | None = None) -> None:
        super().__init__(404, detail or "Resource not found")


class ConflictError(MockMarketAPIError):
    """409 — an invalid lifecycle transition (e.g. pausing a sandbox before start)."""

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(409, detail or "Conflict")


class ValidationError(MockMarketAPIError):
    def __init__(self, detail: str | None = None) -> None:
        super().__init__(422, detail or "Validation error")
