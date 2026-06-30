# AI Pricing Intelligence

Codex Skill project for monitoring global iOS subscription price differences for AI products such as ChatGPT, Claude, Gemini, and Grok.

The core package is `ai-subscription-pricing-intel/`. It captures App Store Price snapshots, parses iOS IAP regional prices, recomputes CNY values with FX rates, performs Apple storefront spot checks, and generates daily Markdown intelligence reports.

## Highlights

- Daily short reports for routine prompts such as `GPT套餐监测`, `Claude套餐监测`, `Gemini套餐监测`, and `Grok套餐监测`
- Full product matrix with fixed columns: plan, cycle, region count, lowest 3 regions with price and FX, US baseline, highest region, discounts, intelligence level, Apple status
- Manual-first snapshot design: local HTML/text is supported; URL capture is explicit
- Source policy that keeps App Store Price, Apple storefront spot checks, FX recomputation, and official plan pages in separate roles
- Generated artifacts are ignored by Git and pruned by retention policy

## Repository Layout

| Path | Purpose |
|---|---|
| `ai-subscription-pricing-intel/` | Canonical Codex Skill package |
| `.github/` | GitHub Actions, issue templates, PR template |
| `.agents/` | Project-local agent metadata |
| `.gitignore` | Keeps snapshots, reports, caches, venvs, and local env files out of Git |
| `README.md` | Repository overview |
| `LICENSE` | MIT license |
| `CHANGELOG.md` | Release notes |
| `CONTRIBUTING.md` | Contribution and validation guide |
| `SECURITY.md` | Security and data-handling policy |
| `RELEASE_CHECKLIST.md` | Pre-publish checklist |

## Skill Package Layout

| Path | Purpose |
|---|---|
| `SKILL.md` | Codex Skill entrypoint and workflow |
| `README.md` | Skill package quick start |
| `config/` | Product routing, retention policy, environment template |
| `references/` | Source policy, field schema, report template, FX policy, environment docs |
| `scripts/` | Capture, parse, FX, enrich, spotcheck, report, cleanup, validation scripts |
| `tests/` | Standard-library tests |
| `data/` | Runtime data directories; only `.gitkeep` should be committed |
| `outputs/` | Generated reports; only `.gitkeep` should be committed |

## Quick Start

Use Python 3.10+; Python 3.12 is recommended. Always run project commands with UTF-8 enabled.

```powershell
cd "E:\AI Pricing Intelligence\ai-subscription-pricing-intel"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -X utf8 scripts/check_environment.py --strict
```

## Daily Monitoring

```powershell
python -X utf8 scripts/collect_appstoreprice_intel.py --today --intent-text "GPT套餐监测"
python -X utf8 scripts/collect_appstoreprice_intel.py --today --intent-text "Claude套餐监测"
python -X utf8 scripts/collect_appstoreprice_intel.py --today --intent-text "Gemini套餐监测"
python -X utf8 scripts/collect_appstoreprice_intel.py --today --intent-text "Grok套餐监测"
```

Reports are written to `ai-subscription-pricing-intel/outputs/`.

## Validation

```powershell
cd "E:\AI Pricing Intelligence\ai-subscription-pricing-intel"
python -X utf8 scripts/check_environment.py --strict
python -X utf8 scripts/check_release_readiness.py --strict
python -X utf8 -m unittest discover -s tests
python -X utf8 -m compileall scripts
python -X utf8 C:\Users\JS\.codex\skills\.system\skill-creator\scripts\quick_validate.py .
```

Full daily monitoring needs outbound HTTPS access to App Store Price, Apple storefront pages, and FX sources. Offline/manual snapshot workflows can use local HTML or copied text instead.

## Data Safety

Do not commit generated snapshots, normalized JSON/CSV, enriched snapshots, FX caches, Apple spotcheck JSON, Markdown reports, `.env` files, credentials, cookies, or account-specific data.

The project intentionally preserves runtime directories with `.gitkeep` while ignoring generated content.

See `ai-subscription-pricing-intel/references/environment.md` for the complete setup checklist, network allowlist, validation commands, and routine monitoring commands.
