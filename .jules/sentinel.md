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

## 2024-05-24 - [IDNA SSRF Bypass]
**Vulnerability:** The SSRF protection in `mcp/url_policy.py` could be bypassed using IDNA-encoded hostnames (like `①②⑦.⓪.⓪.①`). The Python `socket.getaddrinfo` on some systems would fail to resolve the un-encoded Unicode string, bypassing the check, but `httpx` would IDNA-encode the hostname under the hood, normalize it to `127.0.0.1`, and connect to the internal address.
**Learning:** Security validation logic must process hostnames the exact same way the underlying HTTP client will process them.
**Prevention:** Always IDNA-encode hostnames using `.encode("idna").decode("ascii")` prior to checking them against denylists or attempting IP resolution.
