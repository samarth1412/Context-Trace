class ContextTraceError(Exception):
    """Base SDK error."""


class ContextTraceConfigError(ContextTraceError):
    """Raised when SDK configuration is invalid."""


class ContextTraceHTTPError(ContextTraceError):
    """Raised when the ContextTrace API request fails."""


class ContextTraceLocalError(ContextTraceError):
    """Raised when local trace storage cannot satisfy a request."""
