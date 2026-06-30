# Source Policy

Use this policy when producing iOS regional subscription price-gap intelligence.

## Source Priority

| Priority | Source | Use for | Label |
|---:|---|---|---|
| 1 | App Store Price app regional table | Full country/region iOS IAP ranking, local price, CNY conversion, lowest/highest status, saving percentage | `aggregated` |
| 2 | Apple App Store country storefront page | Spot-checking individual storefront prices for selected regions | `apple_spot_checked` |
| 3 | FX source | Recomputing CNY values for comparison only | `fx_checked` |
| 4 | Official provider pricing or subscription page | Confirming product ownership, plan family, and rough plan naming only | `official_context` |
| 5 | News, social, community posts | Early warning or lead generation only | `unconfirmed_lead` |

## Non-Override Rules

- App Store Price is the full-region iOS IAP aggregation source.
- Apple storefront pages are spot-check sources, not replacements for the aggregation table.
- Official pricing pages are only for plan attribution and naming. Do not use official Web prices to override iOS IAP regional prices.
- FX sources only recompute CNY for comparison. Do not overwrite App Store Price `source_cny_price`.
- If sources conflict, present the conflicting values side by side and mark the conflict. Do not automatically merge, average, or choose a silent winner.

## Accuracy Rules

- Prefer manual snapshots from local HTML or copied text. Do not hard-crawl App Store Price by default.
- URL snapshot capture is allowed only when the user explicitly provides a URL for capture.
- Use `balanced` as the default monitoring accuracy mode: spot-check the detailed plan's lowest 3 regions, United States baseline, and highest region.
- Use `light` only when speed is preferred: App Store Price plus FX recomputation, with Apple storefront spot checks left manual.
- Use `high` when confidence matters more than speed: spot-check Top 10 low-price regions, United States, and Top 5 high-price regions for the detailed plan.
- If App Store Price and Apple storefront data disagree, keep both values and set `verification_status` to `conflict`.
- If a storefront cannot be opened or parsed, keep the App Store Price row and set `spotcheck_status` to `failed`.

## Required Report Labels

- `聚合价`: price from App Store Price.
- `Apple 抽样价`: value checked on an Apple storefront page.
- `汇率复算价`: local price recomputed to CNY using the selected FX source.
- `待复核价`: App Store Price row that has not been spot-checked.
- `冲突价`: Apple storefront, FX recomputation, and/or App Store Price values differ beyond the configured threshold.

## Restrictions

Do not provide cross-region purchase tutorials. Do not judge cross-region subscription feasibility.
