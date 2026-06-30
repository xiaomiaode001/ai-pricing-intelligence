# Field Schema

Use these fields for product routing, snapshot capture, App Store Price parsing, iOS regional price normalization, FX verification, Apple storefront spot checks, snapshot comparison, and intelligence reporting.

## Product Routing Fields

| Field | Meaning | Example |
|---|---|---|
| `product_key` | Configured product key | `chatgpt`, `claude`, `gemini` |
| `aliases` | Natural-language triggers for product routing | `GPT套餐监测`, `Gemini 套餐监测` |
| `default_report_plan` | Plan used for detailed report sections when `--report-plan` is omitted | `ChatGPT Plus 1月` |
| `official_pricing_url` | Official page used only for naming/product context | `https://chatgpt.com/pricing/` |
| `monitor_date` | Local date for today's monitoring run | `2026-06-29` |
| `retention_days` | Number of days generated monitoring artifacts are kept by default | `14` |
| `retain_minimum_per_product` | Minimum recent snapshots kept per product even when older than retention days | `2` |
| `cleanup_status` | Cleanup execution status after collection | `complete`, `dry_run`, `skipped_by_flag`, `disabled_by_config`, `failed` |
| `cleanup_deleted_count` | Number of artifacts deleted by retention cleanup | `8` |
| `cleanup_summary` | JSON cleanup summary returned by the pruning script | `{"expired_snapshot_count": 1}` |
| `accuracy_mode` | Collection accuracy strategy | `light`, `balanced`, `high` |
| `spotcheck_mode` | Effective Apple storefront spotcheck scope | `balanced`, `high`, `top10-low` |
| `report_mode` | Report output depth requested from collection | `daily`, `full`, `both` |
| `daily_report_path` | Daily short report output path | `outputs/chatgpt-6448311069-20260629.daily.md` |
| `full_report_path` | Full 11-module report output path | `outputs/chatgpt-6448311069-20260629.report.md` |

## Snapshot And Capture Fields

| Field | Meaning | Example |
|---|---|---|
| `snapshot_id` | Stable capture id | `chatgpt-6448311069-20260629` |
| `captured_at` | UTC capture timestamp from manifest | `2026-06-29T03:00:00+00:00` |
| `capture_method` | Snapshot input method | `text_file`, `html_file`, `text_inline`, `url_authorized` |
| `parser_version` | Parser version used for downstream parsing | `appstoreprice-parser-v2` |
| `plans_detected` | Plan labels detected in raw source | `["ChatGPT Plus 1月", "ChatGPT Go 1月"]` |
| `plan_count` | Number of distinct plan labels in the product snapshot/report | `6` |
| `region_count` | Region rows parsed for the selected plan | `33` |
| `provider` | Publisher or provider | `OpenAI` |
| `product` | App or subscription family | `ChatGPT` |
| `app_store_id` | Apple app id | `6448311069` |
| `source_url` | App Store Price page URL | `https://appstoreprice.org/zh/apps/6448311069` |
| `raw_snapshot_path` | Saved raw HTML or text path | `data/raw/appstoreprice/.../raw.html` |
| `source_hash` | SHA-256 hash of the saved raw source | `sha256:...` |
| `raw_size_bytes` | UTF-8 byte size of the saved raw source | `438210` |
| `status` | Capture status | `captured`, `failed` |
| `extraction_mode` | Parser/capture extraction path | `catalog`, `html_table`, `copied_text`, `failed`, `missing` |
| `catalog_detected` | Whether embedded App Store Price catalog was found in raw HTML | `true` |
| `catalog_plan_count` | Number of plans found in embedded catalog | `6` |
| `catalog_row_count` | Number of regional price rows found in embedded catalog | `166` |
| `expected_plan_count` | Expected plan count from catalog or detected plan tabs | `6` |
| `quality_status` | Capture quality gate status | `complete`, `partial`, `missing`, `failed` |

## Normalized Regional Price Fields

| Field | Meaning | Example |
|---|---|---|
| `iap_plan_label` | Exact App Store Price plan label | `ChatGPT Plus 1月` |
| `plan_name` | Normalized plan name | `ChatGPT Plus` |
| `billing_cycle` | Billing cadence | `1M`, `1Y`, `usage`, `unknown` |
| `platform_scope` | Pricing platform scope | `iOS IAP` |
| `appstoreprice_rank` | Rank in the regional table | `1` |
| `rank_change` | Rank change versus previous snapshot | `-2`, `0`, `+3` |
| `region` | Region name from App Store Price | `菲律宾` |
| `storefront_country` | Storefront country text | `菲律宾` |
| `iso2` | ISO 3166-1 alpha-2 code | `PH` |
| `iso3` | ISO 3166-1 alpha-3 code | `PHL` |
| `apple_storefront_code` | Apple storefront code | `ph` |
| `apple_storefront_url` | Apple storefront link when visible or generated | `https://apps.apple.com/ph/app/id6448311069` |
| `source_local_price` | Local price from App Store Price | `PHP999 PHP` |
| `local_price_amount` | Numeric local amount parsed from local price | `999` |
| `source_cny_price` | App Store Price CNY conversion; never overwrite | `111.09` |
| `currency` | Currency code | `PHP` |
| `price_status` | Table status | `lowest`, `highest`, `normal`, `unknown` |
| `parse_warning` | Parser warning if source looks incomplete | `row_count_below_expected` |
| `observed_at` | Snapshot observation date | `2026-06-29` |

## FX Recalculation Fields

| Field | Meaning | Example |
|---|---|---|
| `computed_cny_price` | `local_price_amount * fx_rate_to_cny`; never overwrites `source_cny_price` | `111.09` |
| `fx_source` | Rate source used for recomputation | `frankfurter`, `manual_fx_snapshot` |
| `fx_rate_date` | Rate date returned by source | `2026-06-29` |
| `fx_rate_to_cny` | One local currency unit in CNY | `0.1112` |
| `cny_delta` | `computed_cny_price - source_cny_price` | `0.00` |
| `cny_delta_pct` | `cny_delta / source_cny_price * 100` | `0.0` |
| `fx_verification_status` | FX verification result | `fx_checked`, `fx_mismatch`, `fx_missing` |
| `rate_is_latest_business_day` | Whether prior business-day rate was used | `true` |

## Intelligence Metrics

| Field | Meaning | Example |
|---|---|---|
| `lowest_region` | Lowest observed region for selected plan | `菲律宾` |
| `lowest_cny` | Lowest App Store Price CNY price | `111.09` |
| `highest_region` | Highest observed region for selected plan | `哥伦比亚` |
| `highest_cny` | Highest App Store Price CNY price | `199.09` |
| `spread_cny` | `highest_cny - lowest_cny` | `88.00` |
| `saving_pct` | Saving versus highest price from source or computed equivalent | `44` |
| `baseline_region` | Baseline region for intelligence judgement | `美国` |
| `baseline_cny` | Baseline App Store Price CNY | `136.29` |
| `discount_vs_baseline_pct` | `(baseline_cny - lowest_cny) / baseline_cny * 100` | `18.49` |
| `discount_vs_highest_pct` | `(highest_cny - lowest_cny) / highest_cny * 100` | `44.20` |
| `intelligence_level` | Price-gap level | `high`, `medium`, `low`, `none` |
| `lowest_3_regions` | Report display field for the three cheapest regions with local price, source CNY, and FX rate | `菲律宾 PHP999 / ¥111.09 / FX 0.1112` |
| `plan_price_matrix` | Product-level table where each plan row includes region count, lowest 3 regions, US baseline, highest region, discounts, and intelligence level | `ChatGPT Plus 1月 -> lowest 3 ...` |
| `base_output_dimensions` | Required base matrix columns for routine outputs | `套餐, 周期, 地区数, 最低 3 地区 / 价格 / 汇率, 美国基准, 最高地区, 相对美国折扣, 相对最高折扣, 信息差等级, Apple 复核状态` |

## Apple Spotcheck Fields

| Field | Meaning | Example |
|---|---|---|
| `spotcheck_status` | Apple spotcheck execution status | `ok`, `failed` |
| `apple_spotcheck_price` | Apple storefront observed local price string | `PHP999 PHP` |
| `apple_price_raw` | Raw Apple storefront price text | `PHP999 PHP` |
| `apple_local_price_amount` | Numeric Apple price amount | `999` |
| `spotcheck_source` | Spotcheck source | `network`, `fixture` |
| `verification_status` | Apple verification result | `apple_spot_checked`, `conflict`, `manual_review`, `appstoreprice_only` |
| `checked_at` | UTC check timestamp | `2026-06-29T03:05:00+00:00` |

## Snapshot Comparison And Anomaly Fields

| Field | Meaning | Example |
|---|---|---|
| `previous_snapshot_id` | Previous snapshot id used for comparison | `chatgpt-previous` |
| `price_change_pct` | Regional price change versus previous snapshot | `+2.35` |
| `rank_change` | Rank movement versus previous snapshot | `-1` |
| `anomaly_level` | Severity for anomaly display | `none`, `watch`, `review`, `critical` |
| `lowest_region_changed` | Lowest region changed versus previous snapshot | `detected`, `none` |
| `highest_region_changed` | Highest region changed versus previous snapshot | `detected`, `none` |
| `price_change_over_2pct` | Any same-region CNY price changed by more than 2% | `detected`, `none` |
| `price_change_over_5pct` | Any same-region CNY price changed by more than 5% | `detected`, `none` |
| `region_count_drop` | Region count dropped abnormally | `detected`, `none` |
| `plan_added` | New plan detected | `detected`, `none` |
| `plan_removed` | Existing plan disappeared | `detected`, `none` |
| `apple_spotcheck_conflict` | Apple spotcheck conflicts with App Store Price | `detected`, `none` |
| `fx_mismatch_over_threshold` | FX mismatch exceeds 1.5% threshold | `detected`, `none` |

## Normalization Rules

- Preserve exact source strings for `iap_plan_label`, `region`, and `source_local_price`.
- Store CNY comparison values as numbers without the `¥` symbol.
- Keep App Store Price CNY as `source_cny_price`; do not overwrite it with FX or Apple spotcheck results.
- Name Skill recomputed CNY as `computed_cny_price`.
- Every routine output matrix must include the base dimensions in `base_output_dimensions`.
- The `lowest_3_regions` display must include local price, `source_cny_price`, `fx_rate_to_cny`, and `computed_cny_price`.
- If `abs(cny_delta_pct) > 1.5`, set `fx_verification_status` to `fx_mismatch`.
- Normalize `spotcheck_status` to `ok` or `failed`.
- When Apple storefront and App Store Price differ, set `verification_status` to `conflict` and show both values side by side.
- Do not infer cross-region purchase feasibility from any field.
