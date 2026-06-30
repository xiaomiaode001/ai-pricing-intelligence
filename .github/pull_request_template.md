## Summary

- 

## Validation

- [ ] `python -X utf8 scripts/check_environment.py --strict`
- [ ] `python -X utf8 scripts/check_release_readiness.py --strict`
- [ ] `python -X utf8 -m unittest discover -s tests`
- [ ] `python -X utf8 -m compileall scripts`

## Data Safety

- [ ] No generated raw snapshots, normalized JSON/CSV, enriched snapshots, FX caches, reports, or local `.env` files are included.
- [ ] `source_cny_price` is not overwritten by FX or Apple values.
- [ ] No cross-region purchase tutorial or feasibility judgment was added.
