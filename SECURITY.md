# Security Policy

ContextTrace handles traces that may contain proprietary prompts, retrieved documents, user questions, citations, and answer text. Treat trace payloads as sensitive by default.

## Supported Versions

Security fixes are applied to the main branch and the latest stable package.

| Version | Supported |
| --- | --- |
| `main` | Yes |
| `1.x` | Yes |
| `< 1.0` | No |

## Reporting a Vulnerability

Do not open a public GitHub issue for vulnerabilities.

Email the maintainers or use GitHub private vulnerability reporting if it is enabled for the repository. Include:

- affected component
- reproduction steps
- potential impact
- suggested fix, if known

We will acknowledge valid reports as quickly as possible and coordinate a fix before public disclosure.

## Sensitive Data Guidance

- Do not commit real API keys.
- Do not include private customer documents in issues or pull requests.
- Prefer local mode for sensitive traces during development.
- Redact trace metadata before sharing screenshots or reports.
