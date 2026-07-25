"""Shared formatting utilities used across routers and services."""


def format_duration_ms(duration_ms: int | None) -> str:
    """Format a duration in milliseconds to a human-readable string.

    Examples:
        format_duration_ms(None)   -> "—"
        format_duration_ms(0)      -> "0s"
        format_duration_ms(42000)  -> "42s"
        format_duration_ms(192000) -> "3m 12s"
    """
    if not duration_ms:
        return "—"
    secs = duration_ms // 1000
    mins = secs // 60
    secs = secs % 60
    return f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
