# Security, privacy and legal-safety notes

Implemented and tested (see `backend/tests/test_auth_security.py`, `test_isolation.py`, `test_documents.py`):

| Threat | Mitigation |
|---|---|
| Broken authentication | Passwords hashed with scrypt (N=2^14) and per-user salt; random 256-bit session tokens stored only as HMAC-SHA256 digests; HttpOnly + SameSite=Lax cookie (Secure when `NYAYA_COOKIE_SECURE=true`); identical error for unknown user / wrong password; auth endpoints rate-limited (10/min/IP) |
| Broken authorization / cross-user exposure | Every private query filters by `user_id`; foreign ids return 404 (not 403) so ids are not revealed; tested across cases, documents, drafts, conversations, exports and retries |
| CSRF | Unsafe methods require header `X-Requested-With: nyaya` (cannot be sent cross-site without a CORS preflight, which only allowed origins pass) and a matching `Origin` |
| XSS | React escapes output; no `dangerouslySetInnerHTML`; strict CSP (`script-src 'self'`, `frame-ancestors 'none'`), `nosniff`, `Referrer-Policy: no-referrer`; user documents are shown as plain text |
| SQL injection | SQLAlchemy parameterised queries only |
| Malicious uploads | Type decided by magic bytes, not client MIME/extension; size cap; page cap; DOCX zip-bomb check; random on-disk names in a per-user folder (no path traversal); parsers are pure-Python (pypdf/pdfminer/python-docx); text is never executed |
| Prompt injection (uploads / retrieved text) | Uploaded text is never placed in an LLM prompt. The optional generator receives retrieved sources inside delimiters with an instruction to treat them as data, and its output is validated against those sources |
| Retrieval poisoning | The corpus is built only by an operator-run CLI from declared sources with provenance and hashes; there is no user-writable path into the index |
| Fabricated citations | `CitationValidator` strips markers, quotations and URLs that cannot be traced to retrieved passages |
| Resource exhaustion | Rate limit, body-size limit, upload/page caps, inference concurrency cap, request timeout (note: a timed-out Python thread keeps running until it finishes) |
| Log leakage | Request bodies are never logged; audit rows store only ids/actions, not text or file names |
| Secrets | Server-side only; `NYAYA_SECRET_KEY` mandatory in production; `.env` git-ignored |

## Not done / operator responsibilities

* No email verification or password reset (needs an email service). Registration is open.
* Rate limiting is in-process; behind multiple workers use a proxy-level limiter.
* Uploads are stored unencrypted on disk; use disk encryption (BitLocker on Windows) on the host.
* Sessions are not invalidated on password change (no password-change endpoint yet).
* Run behind HTTPS if exposed beyond localhost.
* **Indian law compliance is not assessed.** The Digital Personal Data Protection Act, 2023 and advocates' confidentiality duties may apply to an operator serving the public; these need legal advice. Nothing here claims compliance.
