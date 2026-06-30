# ai-subscription-pricing-intel

Codex Skill for generating iOS global subscription price-gap intelligence for AI apps.

## What It Covers

Default product routes:

| Key | Product | App Store ID | Default detail plan |
|---|---|---|---|
| `chatgpt` | ChatGPT | `6448311069` | `ChatGPT Plus 1月` |
| `claude` | Claude | `6473753684` | `Claude Pro 1月` |
| `gemini` | Google Gemini | `6477489729` | `Google AI Pro (5 TB) 1月` |
| `grok` | Grok | `6670324846` | `SuperGrok 1月` |

## Source Policy

- App Store Price is the primary full-region iOS IAP aggregation source.
- Apple storefront pages are sampled spot checks only.
- FX sources recompute CNY for verification only.
- Official provider pages are naming and product-context references only.
- Conflicting values must be shown side by side and never silently merged.

## Install

```powershell
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

Daily reports are written to `outputs/<snapshot_id>.daily.md`.

## Report Baseline Columns

The product matrix uses these fixed columns:

| 套餐 | 周期 | 地区数 | 最低 3 地区 / 价格 / 汇率 | 美国基准 | 最高地区 | 相对美国折扣 | 相对最高折扣 | 信息差等级 | Apple 复核状态 |
|---|---|---|---|---|---|---|---|---|---|

## Validation

```powershell
python -X utf8 scripts/check_environment.py --strict
python -X utf8 scripts/check_release_readiness.py --strict
python -X utf8 -m unittest discover -s tests
python -X utf8 -m compileall scripts
```

Official Skill validation:

```powershell
python -X utf8 C:\Users\JS\.codex\skills\.system\skill-creator\scripts\quick_validate.py .
```

## Runtime Data

Generated snapshots, normalized files, FX caches, spot checks, and reports live in `data/` and `outputs/`. They are ignored by Git except for `.gitkeep`.
