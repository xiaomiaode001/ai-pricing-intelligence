# Release Checklist

Use this before publishing the repository to GitHub.

## Required Files

- [ ] `README.md`
- [ ] `LICENSE`
- [ ] `CHANGELOG.md`
- [ ] `CONTRIBUTING.md`
- [ ] `SECURITY.md`
- [ ] `CODE_OF_CONDUCT.md`
- [ ] `.gitignore`
- [ ] `.gitattributes`
- [ ] `.github/workflows/validate.yml`
- [ ] `.github/ISSUE_TEMPLATE/bug_report.yml`
- [ ] `.github/ISSUE_TEMPLATE/feature_request.yml`
- [ ] `.github/pull_request_template.md`
- [ ] `ai-subscription-pricing-intel/README.md`
- [ ] `ai-subscription-pricing-intel/SKILL.md`

## Validation

```powershell
cd ai-pricing-intelligence/ai-subscription-pricing-intel
python -m pip install -r requirements.txt
python -X utf8 scripts/check_environment.py --strict
python -X utf8 scripts/check_release_readiness.py --strict
python -X utf8 -m unittest discover -s tests
python -X utf8 -m compileall scripts
```

Run official Skill validation:

```powershell
python -X utf8 "<path-to-skill-creator>/scripts/quick_validate.py" .
```

## Data Safety

- [ ] No files under `data/raw/appstoreprice/` except `.gitkeep`
- [ ] No files under `data/normalized/` except `.gitkeep`
- [ ] No files under `data/snapshots/` except `.gitkeep`
- [ ] No files under `data/fx/` except `.gitkeep`
- [ ] No files under `outputs/` except `.gitkeep`
- [ ] No `.env`, credentials, cookies, or account-specific files

## GitHub Setup

- [ ] Add GitHub remote
- [ ] Push default branch
- [ ] Confirm GitHub Actions validation passes
- [ ] Create first release tag, for example `v0.1.0`
