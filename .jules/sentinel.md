## 2024-05-14 - [CRITICAL] Prevented SSRF Bypass with IPv6 Support
**Vulnerability:** The initial SSRF fix in `mcp/url_policy.py` only used `socket.gethostbyname()`, which fails for IPv6 literals (e.g., `http://[::1]/`). Because the exception was silently caught to allow failing DNS, IPv6 internal requests bypassed the protection.
**Learning:** `socket.gethostbyname()` is insufficient for thorough SSRF checks since it only handles IPv4.
**Prevention:** Use `socket.getaddrinfo()` instead, which resolves both IPv4 and IPv6 addresses. Alternatively, use `ipaddress.ip_address` to directly parse and validate IPv6 literals if passed in the URL.
## 2024-05-15 - [CRITICAL] Prevented SSRF Bypass with 0.0.0.0 and Multicast
**Vulnerability:** The SSRF protection only blocked loopback, private, and link-local IP addresses. It allowed requests to 0.0.0.0 (unspecified) which on some systems resolves to localhost, effectively bypassing loopback checks.
**Learning:** When implementing SSRF protection, "private/loopback" checks are not enough. You must also block unspecified (0.0.0.0), multicast, and reserved IPs.
**Prevention:** Add `is_unspecified`, `is_reserved`, and `is_multicast` checks to IP validation logic.

## 2024-05-18 - [SSRF Bypass via Trailing Dot (FQDN)]
**Vulnerability:** The SSRF protection logic in `url_policy.py` validated hostnames directly from `urllib.parse.urlsplit` without stripping trailing dots. Hostnames ending with a dot (e.g. `localhost.` or `127.0.0.1.`) would bypass strict string matching (`== "localhost"`) and cause `socket.getaddrinfo()` to fail (which was caught and allowed as "fail-open"). The underlying HTTP client could still resolve and connect to the internal IP.
**Learning:** Fully Qualified Domain Names (FQDNs) with a trailing root dot bypass naive blocklists. Trailing dots can also break naive DNS validation wrappers depending on the OS resolver implementation while still being parsed successfully by the target HTTP client.
**Prevention:** Always normalize the hostname by calling `.rstrip('.')` on the parsed hostname string before performing validation checks or DNS resolution in SSRF protections.
## 2024-05-28 - [CRITICAL] Prevented Timing Attack on API Token Validation
**Vulnerability:** The API token validation in `mcp/api.py` used direct string comparison (`!=`) for bearer tokens. This is vulnerable to timing attacks, as string comparison operators stop at the first differing character, leaking the length of the matched prefix.
**Learning:** Never use `==` or `!=` for comparing cryptographic secrets, passwords, or authentication tokens.
**Prevention:** Always use `secrets.compare_digest()` for comparing sensitive tokens to ensure constant-time comparison.
