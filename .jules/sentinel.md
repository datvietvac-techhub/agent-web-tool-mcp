## 2024-05-21 - [Prevent Timing Attack in API Token Validation]
**Vulnerability:** The API token validation used standard string equality comparison (`credentials.credentials != API_TOKEN`), which is vulnerable to timing attacks. This could theoretically allow an attacker to guess the `API_TOKEN` by observing minor differences in response times.
**Learning:** Found string comparison used for security-critical authentication keys instead of constant-time comparisons.
**Prevention:** Always use `secrets.compare_digest` for validating authentication tokens, HMACs, or other secrets to ensure constant-time comparison and prevent timing attacks.
