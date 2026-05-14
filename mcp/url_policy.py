"""URL validation hooks for web extraction.

This module is intentionally small and permissive today. It gives the extractor
a single policy boundary that can grow later with optional SSRF hardening such
as private-IP blocking, allow/deny lists, and DNS resolution safeguards.
"""

from urllib.parse import urlsplit

ALLOWED_SCHEMES = {"http", "https"}


def validate_fetch_url(url: str) -> str | None:
    """Return an error string when a URL should not be fetched."""
    if not url.strip():
        return "url is required"

    try:
        parts = urlsplit(url.strip())
    except ValueError as exc:
        return f"invalid url: {exc}"

    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        return "url scheme must be http or https"
    if not parts.netloc or not parts.hostname:
        return "url must include a host"
    return None
