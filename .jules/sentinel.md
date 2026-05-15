## 2024-05-14 - [CRITICAL] Prevented SSRF Bypass with IPv6 Support
**Vulnerability:** The initial SSRF fix in `mcp/url_policy.py` only used `socket.gethostbyname()`, which fails for IPv6 literals (e.g., `http://[::1]/`). Because the exception was silently caught to allow failing DNS, IPv6 internal requests bypassed the protection.
**Learning:** `socket.gethostbyname()` is insufficient for thorough SSRF checks since it only handles IPv4.
**Prevention:** Use `socket.getaddrinfo()` instead, which resolves both IPv4 and IPv6 addresses. Alternatively, use `ipaddress.ip_address` to directly parse and validate IPv6 literals if passed in the URL.
## 2024-05-15 - [CRITICAL] Prevented SSRF Bypass with 0.0.0.0 and Multicast
**Vulnerability:** The SSRF protection only blocked loopback, private, and link-local IP addresses. It allowed requests to 0.0.0.0 (unspecified) which on some systems resolves to localhost, effectively bypassing loopback checks.
**Learning:** When implementing SSRF protection, "private/loopback" checks are not enough. You must also block unspecified (0.0.0.0), multicast, and reserved IPs.
**Prevention:** Add `is_unspecified`, `is_reserved`, and `is_multicast` checks to IP validation logic.
