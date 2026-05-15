"""URL validation hooks for web extraction.

This module is intentionally small and permissive today. It gives the extractor
a single policy boundary that can grow later with optional SSRF hardening such
as private-IP blocking, allow/deny lists, and DNS resolution safeguards.
"""

from urllib.parse import urlsplit
import socket
import ipaddress

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

    hostname = parts.hostname.lower()

    if (
        hostname == "localhost"
        or hostname.endswith(".local")
        or hostname.endswith(".internal")
    ):
        return "url uses a disallowed internal hostname"

    # SSRF protection: block private, loopback, and link-local IP addresses

    # Try resolving IPv4 and IPv6
    try:
        # socket.getaddrinfo handles both IPv4 and IPv6
        addrinfo = socket.getaddrinfo(hostname, None)
        for result in addrinfo:
            ip = result[4][0]
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.is_loopback or ip_obj.is_private or ip_obj.is_link_local:
                return "url resolves to a disallowed internal IP address"
    except (socket.gaierror, ValueError):
        # If DNS resolution or IP parsing fails, keep policy fail-open for now:
        # only positively identified internal IPs are blocked.
        return None

    return None
