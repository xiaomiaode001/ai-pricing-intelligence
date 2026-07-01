# Contributing

Thanks for improving AI Pricing Intelligence. The project is a Codex Skill package plus supporting scripts for iOS subscription price monitoring.

## Local Setup

```powershell
git clone https://github.com/xiaomiaode001/ai-pricing-intelligence.git
cd ai-pricing-intelligence/ai-subscription-pricing-intel
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -X utf8 scripts/check_environment.py --strict
```

For macOS/Linux, use `source .venv/bin/activate` instead of the PowerShell activation command.

Use `python -X utf8` for all commands so Chinese plan names, region names, and currency symbols render correctly.

## Development Rules

- Keep App Store Price as the primary iOS IAP regional aggregation source.
- Do not overwrite `source_cny_price` with FX recomputation or Apple spot checks.
- Do not add cross-region purchase tutorials or feasibility judgments.
- Keep generated files under `data/` and `outputs/`; they are ignored by Git.
- Preserve the daily report matrix columns: plan, cycle, region count, lowest 3 regions with price and FX, US baseline, highest region, US discount, highest discount, intelligence level, Apple status.

## Validation

Run these before opening a pull request:

```powershell
cd ai-pricing-intelligence/ai-subscription-pricing-intel
python -X utf8 -m unittest discover -s tests
python -X utf8 -m compileall scripts
python -X utf8 scripts/check_environment.py --strict
python -X utf8 scripts/check_release_readiness.py --strict
```

Optional official Codex Skill validation, if the Codex skill creator is installed locally:

```powershell
python -X utf8 "<path-to-skill-creator>/scripts/quick_validate.py" .
```

The official `quick_validate.py` requires `PyYAML`, which is included in `requirements.txt`.

## Pull Request Checklist

- Describe what changed and why.
- Include validation output.
- Confirm no generated snapshots, FX cache files, reports, or local `.env` files are included.
- Mention any source-policy or report-format impact.
