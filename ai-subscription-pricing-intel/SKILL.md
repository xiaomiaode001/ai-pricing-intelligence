---
name: ai-subscription-pricing-intel
description: Generate intuitive iOS global subscription price-gap intelligence for AI apps such as ChatGPT, Claude, Google Gemini, and Grok. Use when asked to capture today's App Store Price snapshot, parse regional iOS subscription prices, compare low-price and high-price storefronts, recalculate App Store Price CNY values with FX rates, spot-check Apple storefront prices, detect snapshot anomalies, or produce source-backed visual Markdown price-gap reports.
---

# AI Subscription Pricing Intel

## Overview

Run a manual-first intelligence workflow for global iOS subscription price gaps. Treat App Store Price as the full-region aggregation source, Apple storefront pages as spot-check evidence, official provider pages only as product/plan naming context, and FX recomputation only as a CNY verification layer.

Default accuracy mode is `balanced`: capture App Store Price, recompute CNY with FX, and spot-check the detailed plan on Apple storefronts for the lowest 3 regions, the United States baseline, and the highest region.

Default report mode is `daily`: produce a short, readable report for routine prompts such as `GPT套餐监测`, `Gemini套餐监测`, or `Claude套餐监测`.

## Product Routing

Use `config/product-monitoring.yml` as the product routing source for GPT/ChatGPT, Claude, Gemini, and optional configured products such as Grok.

- Natural-language input examples:
  - `GPT套餐监测`
  - `ChatGPT套餐监测`
  - `Claude套餐监测`
  - `Gemini套餐监测`
  - `Grok套餐监测`
  - `Gork套餐监测`
- CLI app keys:
  - `chatgpt`
  - `claude`
  - `gemini`
  - `grok`

Default detailed report plans:

- ChatGPT: `ChatGPT Plus 1月`
- Claude: `Claude Pro 1月`
- Gemini: `Google AI Pro (5 TB) 1月`
- Grok: `SuperGrok 1月`

If the configured default plan is not present in the current snapshot, fall back to the first detected plan and mark `default_report_plan_missing` in collection warnings.

## Workflow

1. For routine monitoring, capture the configured App Store Price URL as today's snapshot.

   ```powershell
   python -X utf8 scripts/check_environment.py
   python -X utf8 scripts/collect_appstoreprice_intel.py --today --intent-text "GPT套餐监测"
   python -X utf8 scripts/collect_appstoreprice_intel.py --today --intent-text "Gemini套餐监测"
   python -X utf8 scripts/collect_appstoreprice_intel.py --today --intent-text "Claude套餐监测"
   ```

2. Choose accuracy mode only when the default is not enough:

   - `--accuracy-mode light`: App Store Price + FX only; Apple spotcheck is manual.
   - `--accuracy-mode balanced`: default; spot-check lowest 3 regions, United States, and highest region for the detailed plan.
   - `--accuracy-mode high`: spot-check Top 10 low-price regions, United States, and Top 5 high-price regions for the detailed plan.

   ```powershell
   python -X utf8 scripts/collect_appstoreprice_intel.py --today --intent-text "GPT套餐监测" --accuracy-mode high
   ```

3. Choose report mode only when the default daily short report is not enough:

   - `--report-mode daily`: default; write `outputs/<snapshot_id>.daily.md`.
   - `--report-mode full`: write the full 11-module report to `outputs/<snapshot_id>.report.md`.
   - `--report-mode both`: write both files.

   ```powershell
   python -X utf8 scripts/collect_appstoreprice_intel.py --today --intent-text "GPT套餐监测" --report-mode both
   ```

4. Today's monitoring snapshot id uses `<product_key>-<app_store_id>-YYYYMMDD`, for example `gemini-6477489729-20260629`.

5. Today's monitoring run automatically applies the retention policy from `config/retention.yml`: keep generated artifacts for 14 days and always keep at least the latest 2 snapshots per product.

6. Use `--cleanup-dry-run` to preview cleanup after a monitoring run, or `--skip-cleanup` to keep all generated artifacts for that run.

   ```powershell
   python -X utf8 scripts/collect_appstoreprice_intel.py --today --intent-text "Gemini套餐监测" --cleanup-dry-run
   python -X utf8 scripts/collect_appstoreprice_intel.py --today --intent-text "Gemini套餐监测" --skip-cleanup
   ```

7. Prefer local HTML or copied text only for manual verification, offline reruns, or regression tests.

   ```powershell
   python -X utf8 scripts/collect_appstoreprice_intel.py --html-file page.html --app chatgpt
   ```

8. Use raw `--url` capture only when the user explicitly provides or authorizes a specific URL. For product monitoring, prefer `--today` because it uses the configured product URL and daily snapshot naming.

   ```powershell
   python -X utf8 scripts/collect_appstoreprice_intel.py --url https://appstoreprice.org/zh/apps/6448311069 --app chatgpt --spotcheck
   ```

9. Omit `--plan` for a full product matrix across every detected iOS plan.

10. Use `--plan` only when the user wants to parse one specific plan.

11. Use `--report-plan` only when the user wants the detailed plan sections to focus on a plan other than the configured default.

12. Use the step-by-step scripts only for debugging or compatibility:
   - `scripts/fetch_appstoreprice_snapshot.py`
   - `scripts/parse_appstoreprice_snapshot.py`
   - `scripts/fetch_fx_rates.py`
   - `scripts/enrich_with_fx.py`
   - `scripts/fetch_apple_storefront_spotcheck.py`
   - `scripts/compare_snapshots.py`
   - `scripts/generate_intel_report.py`

## Reference Files

- `config/product-monitoring.yml`: product keys, aliases, App Store Price URLs, and default detailed report plans.
- `config/retention.yml`: generated artifact retention days, minimum snapshots to keep per product, and cleanup protection rules.
- `config/environment.example.yml`: environment checklist template for Python, network, runtime dirs, and validation.
- `references/source-policy.md`: source authority, conflict handling, and no-overwrite rules.
- `references/field-schema.md`: normalized row fields, FX fields, spotcheck fields, parser metadata, and product routing fields.
- `references/fx-source-policy.md`: FX source priority and required rate fields.
- `references/country-storefront-map.yml`: region, ISO, Apple storefront code, and currency map.
- `references/report-template.md`: final report structure.
- `references/environment.md`: setup steps, requirements, network allowlist, validation commands, and routine commands.

## Reporting Rules

- Keep the report centered on iOS IAP regional prices, not Android, web billing, API, Team, Enterprise, or cross-region purchase instructions.
- For routine monitoring, use the daily short report structure: 结论卡片, 全套餐价格矩阵, 重点套餐详情, 最低 3 地区, 准确性复核, Sources.
- Use the fixed 11-module full report only when `--report-mode full` or `--report-mode both` is requested: 结论卡片, 套餐发现结果, 单套餐全球概览, Top 10 低价区, Top 5 高价区, 汇率复算摘要, Apple storefront 抽样复核, 与上一快照对比, 信息差判断, 准确性与限制, Sources.
- Default depth is: full product plan matrix plus one detailed plan section in a short daily report.
- Treat the product plan matrix as the base output for every routine answer and report.
- The base product matrix columns are: 套餐, 周期, 地区数, 最低 3 地区 / 价格 / 汇率, 美国基准, 最高地区, 相对美国折扣, 相对最高折扣, 信息差等级, Apple 复核状态.
- The `最低 3 地区 / 价格 / 汇率` cell must include each low-price region, local price, `source_cny_price`, `fx_rate_to_cny`, and `computed_cny_price`.
- The product plan matrix must include every `plans_detected` item. If a plan tab is detected but no regional price rows were captured, mark the plan row as `needs_snapshot`.
- In the product plan matrix, show Apple status as `apple_spot_checked`, `pending_spotcheck`, `conflict`, or `spotcheck_failed`. Only the detailed report plan is spot-checked by default.
- For low-price monitoring, always show the lowest 3 regions with region, local price, `source_cny_price`, `fx_rate_to_cny`, `computed_cny_price`, and FX status.
- Preserve provider-specific plan labels from App Store Price. Do not force Gemini or Claude plans into ChatGPT naming.
- Keep App Store Price CNY as `source_cny_price`; never overwrite it with FX recomputation or Apple spotcheck results.
- Name Skill recomputed CNY as `computed_cny_price`.
- If `source_cny_price` and `computed_cny_price` differ by more than 1.5%, mark `fx_mismatch`.
- If App Store Price, Apple storefront, or FX recomputation disagree, show the values side by side and mark `conflict`.
- Apply information-gap levels: `high` when lowest is more than 15% below United States or more than 35% below highest; `medium` when lowest is 5% to 15% below United States; `low` when lowest is less than 5% below United States; `none` when lowest is close to or above United States.
- Usage-style plans such as credits or token packs may have fewer regions and should not be treated as ordinary subscription region-count failures.
- Surface anomaly codes: `lowest_region_changed`, `highest_region_changed`, `price_change_over_2pct`, `price_change_over_5pct`, `region_count_drop`, `plan_added`, `plan_removed`, `apple_spotcheck_conflict`, `fx_mismatch_over_threshold`.
- Treat collection summary warnings as audit signals. Do not hide `capture_failed`, `plans_without_rows`, `default_report_plan_missing`, `fx_missing`, `fx_mismatch_over_threshold`, `missing_iso`, `low_region_count`, `apple_spotcheck_failed`, or `apple_spotcheck_conflict`.
- Treat cleanup summary fields as operational metadata. Do not put full cleanup logs into the reader-facing report unless the user asks.
- Do not provide cross-region purchase tutorials and do not judge cross-region subscription feasibility.

## ChatGPT Gold Sample

Use this sample to sanity-check extraction:

- Product: `ChatGPT`
- Plan: `ChatGPT Plus 1月`
- Full product matrix: 6 plans, 166 regional rows
- Selected plan row count: 33
- Lowest: Philippines / `PHP999 PHP` / about `¥111`
- Baseline: United States / `$19.99 USD` / about `¥136`
- Highest: Colombia / `COP99,900 COP` / about `¥199`
- Saving vs highest: about `44%`
