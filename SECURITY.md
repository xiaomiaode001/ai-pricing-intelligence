# Security Policy

## Supported Scope

This project is a local Codex Skill for public iOS subscription price monitoring. It does not require API keys, credentials, payment details, or private account data.

## Reporting a Vulnerability

Please open a private security advisory if the repository is hosted under an organization that supports advisories. Otherwise, contact the repository owner directly and avoid posting exploit details in public issues.

Include:

- affected file or script
- reproduction steps
- expected impact
- suggested mitigation, if known

## Data Handling

- Do not commit generated raw snapshots, normalized price data, FX caches, reports, or local environment files.
- Do not add credentials or cookies to configs, fixtures, reports, or tests.
- Apple storefront spot checks are best-effort public page checks and must not rely on private Apple account sessions.

## Source Integrity

If App Store Price, Apple storefront, or FX values disagree, reports must show values side by side and mark the conflict instead of silently merging or overwriting source values.
