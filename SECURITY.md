# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.2.x   | Yes                |
| < 0.2   | No                 |

## Reporting a Vulnerability

If you discover a security vulnerability in The Embedinator, please report it
responsibly. **Do not open a public GitHub issue for security vulnerabilities.**

### How to Report

Send an email to **embedinator-security@proton.me** with:

- A description of the vulnerability
- Steps to reproduce the issue
- The potential impact
- Any suggested fixes (optional)

### What to Expect

- **Acknowledgment**: We will acknowledge your report within **48 hours**.
- **Updates**: We will provide status updates as we investigate and work on a fix.
- **Resolution**: We aim to resolve confirmed vulnerabilities within **90 days**
  of the initial report.
- **Disclosure**: We follow a **90-day coordinated disclosure** policy. After a
  fix is released, we will publicly disclose the vulnerability with credit to
  the reporter (unless anonymity is requested).

### Scope

This policy applies to the following components:

- The Embedinator backend (Python/FastAPI)
- The Embedinator frontend (Next.js)
- The ingestion worker (Rust)
- Docker Compose configuration and launcher scripts
- CI/CD workflows and GitHub Actions

### Out of Scope

- Third-party dependencies (report to the respective maintainers)
- Issues in Docker, Qdrant, or Ollama themselves
- Social engineering attacks

## Security Design

The Embedinator is designed as a **local-first, self-hosted** application:

- All data stays on your machine (SQLite + Qdrant in Docker volumes)
- API keys are encrypted at rest using Fernet symmetric encryption
- No telemetry or external data collection
- No authentication by default (designed for trusted local network use)

For production deployments, see the [runbook](docs/runbook.md) for TLS and
reverse proxy configuration.
