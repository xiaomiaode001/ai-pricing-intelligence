# Environment Setup

This Skill is designed to run with a small Python environment. Runtime scripts use the Python standard library; `PyYAML` is included for complete Codex Skill validation because the official `quick_validate.py` imports `yaml`.

## Required Runtime

| Item | Requirement |
|---|---|
| OS | Windows PowerShell supported; other shells can run the same Python scripts |
| Python | 3.10+ required, 3.12 recommended |
| Encoding | Run commands with `python -X utf8` or set `PYTHONUTF8=1` |
| Network | Needed for `--today`, App Store Price URL capture, FX refresh, and Apple storefront spot checks |
| Secrets | No API key is required |

## Install

From `E:\AI Pricing Intelligence\ai-subscription-pricing-intel`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If activation is not desired, run with the system Python and install the same requirements there.

## Validate

```powershell
python -X utf8 scripts/check_environment.py
python -X utf8 scripts/check_environment.py --network
python -X utf8 C:\Users\JS\.codex\skills\.system\skill-creator\scripts\quick_validate.py .
```

Use `--strict` when preparing the project for another user; it treats warnings as failures.

```powershell
python -X utf8 scripts/check_environment.py --strict
```

## Network Allowlist

Allow outbound HTTPS to these hosts for full monitoring:

| Host | Purpose |
|---|---|
| `appstoreprice.org` | Full-region iOS IAP aggregation source |
| `apps.apple.com` | Apple storefront spot checks |
| `api.frankfurter.dev` | Primary FX source |
| `frankfurter.app` | Frankfurter fallback endpoint |
| `open.er-api.com` | ExchangeRate-API fallback |

If network access is unavailable, use local snapshot modes:

```powershell
python -X utf8 scripts/collect_appstoreprice_intel.py --html-file page.html --app chatgpt
python -X utf8 scripts/collect_appstoreprice_intel.py --text-file page.txt --app chatgpt
```

## Configuration Files

| File | Purpose |
|---|---|
| `config/product-monitoring.yml` | Product routes, aliases, App Store Price URLs, default detailed plan |
| `config/retention.yml` | Generated artifact retention policy |
| `config/environment.example.yml` | Human-readable environment template |
| `requirements.txt` | Python package dependencies for validation |

## Routine Commands

```powershell
python -X utf8 scripts/collect_appstoreprice_intel.py --today --intent-text "GPT套餐监测"
python -X utf8 scripts/collect_appstoreprice_intel.py --today --intent-text "Gemini套餐监测"
python -X utf8 scripts/collect_appstoreprice_intel.py --today --intent-text "Claude套餐监测"
python -X utf8 scripts/collect_appstoreprice_intel.py --today --intent-text "Grok套餐监测"
```

Generated data is written inside `data/` and `outputs/`, then pruned according to `config/retention.yml`.
