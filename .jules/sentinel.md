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

## 2024-05-20 - [HIGH] Prevented Timing Attack in Token Validation
**Vulnerability:** The API token verification in `mcp/api.py` used standard string comparison (`!=`) instead of a constant-time comparison, making it susceptible to timing attacks where an attacker could incrementally guess the token.
**Learning:** Standard string comparisons evaluate character by character and return early on the first mismatch. This allows attackers to measure the time taken to reject a request to infer the correctness of individual characters.
**Prevention:** Always use `secrets.compare_digest()` for comparing sensitive tokens, hashes, or passwords to ensure constant-time comparison and prevent timing attacks.
