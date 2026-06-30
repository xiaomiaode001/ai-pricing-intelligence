# Report Template

Write reports in Chinese unless the user asks otherwise. Prefer `scripts/generate_intel_report.py` for final output so labels, ordering, conflict wording, and price fields stay stable.

The default report mode is `daily`: a short product-level price intelligence report with a full plan matrix plus one detailed plan section. Use `full` only when the user asks for the complete 11-module report.

## Daily Modules

Daily reports must use these 6 modules in this order:

1. 结论卡片
2. 全套餐价格矩阵
3. 重点套餐详情
4. 最低 3 地区
5. 准确性复核
6. Sources

Daily reports must not include long raw metadata, full Top 10 / Top 5 tables, or the full anomaly-code table.

## Full Modules

Full reports must use these 11 modules in this order:

1. 结论卡片
2. 套餐发现结果
3. 单套餐全球概览
4. Top 10 低价区
5. Top 5 高价区
6. 汇率复算摘要
7. Apple storefront 抽样复核
8. 与上一快照对比
9. 信息差判断
10. 准确性与限制
11. Sources

## Opening Rules

The report opening must first answer:

- 最低地区
- 最高地区
- 价差空间
- 相对最高价省幅
- 信息差等级

## 全套餐价格矩阵

This section is product-level. Include every detected iOS plan in one matrix.

Required columns:

| 套餐 | 周期 | 地区数 | 最低 3 地区 / 价格 / 汇率 | 美国基准 | 最高地区 | 相对美国折扣 | 相对最高折扣 | 信息差等级 | Apple 复核状态 |
|---|---|---:|---|---|---|---:|---:|---|---|

Rules:

- Treat this matrix as the base output dimension set for every daily answer and generated report.
- The `最低 3 地区 / 价格 / 汇率` cell must show, for each of the three cheapest regions: region, local price, `source_cny_price`, `fx_rate_to_cny`, and `computed_cny_price`.
- `美国基准`, `最高地区`, and `相对美国折扣` are required base dimensions, not optional detail fields.
- Preserve exact App Store Price `iap_plan_label`.
- Do not force Gemini or Claude plans into ChatGPT naming.
- If a detected plan has no captured price rows, set low-price cells and `信息差等级` to `needs_snapshot`.
- Show Apple status as `apple_spot_checked`, `pending_spotcheck`, `conflict`, `spotcheck_failed`, or `needs_snapshot`.
- Usage-style plans such as credits or token packs can have fewer regions.

## 单套餐全球概览

This section is detailed-plan-level. By default, use the configured default plan from `config/product-monitoring.yml`.

Required overview columns:

| 产品 | iOS 套餐 | 地区数 | 最低地区 | 最低 CNY | 美国基准 CNY | 最高地区 | 最高 CNY | 差额 CNY | 信息差等级 |
|---|---|---:|---|---:|---:|---|---:|---:|---|

Required lowest-3 columns:

| 低价排名 | 地区 | ISO2 | 原币价格 | source_cny_price | fx_rate_to_cny | computed_cny_price | FX 状态 |
|---:|---|---|---:|---:|---:|---:|---|

Daily report lowest-3 columns:

| 排名 | 地区 | ISO2 | 原币价格 | source_cny_price | FX | computed_cny_price | FX 状态 | Apple 复核 |
|---:|---|---|---:|---:|---:|---:|---|---|

## Top Lists

Top 10 low-price and Top 5 high-price tables must include:

| 排名 | 地区 | ISO2 | 聚合价 | source_cny_price | computed_cny_price | 偏差 | Apple 抽样 |
|---:|---|---|---:|---:|---:|---:|---|

## 汇率复算摘要

Required fields:

- 使用汇率源
- 汇率日期
- FX 检查阈值：`1.5%`
- 复算结论
- 是否覆盖 `source_cny_price`：否

Rules:

- Keep App Store Price CNY as `source_cny_price`.
- Name Skill recomputed CNY as `computed_cny_price`.
- Do not use `computed_cny_price` to overwrite `source_cny_price`.
- If `abs(cny_delta_pct) > 1.5`, mark `fx_mismatch`.

## Apple storefront 抽样复核

Required columns:

| 地区 | App Store Price 聚合价 | Apple 抽样价 | spotcheck_status | verification_status |
|---|---:|---:|---|---|

Rules:

- Apple storefront only spot-checks App Store Price.
- Do not use Apple spotcheck values to overwrite App Store Price aggregated values.
- If values conflict, show both and mark `conflict`.
- Default accuracy mode is `balanced`: spot-check the detailed plan's lowest 3 regions, United States baseline, and highest region.
- `high` mode expands spot checks to Top 10 low-price regions, United States, and Top 5 high-price regions.
- `light` mode keeps Apple storefront spot checks manual.

## 与上一快照对比

Show these anomaly codes:

- `lowest_region_changed`
- `highest_region_changed`
- `price_change_over_2pct`
- `price_change_over_5pct`
- `region_count_drop`
- `plan_added`
- `plan_removed`
- `apple_spotcheck_conflict`
- `fx_mismatch_over_threshold`

## 信息差等级

- `high`: lowest price is more than 15% below the United States baseline, or more than 35% below the highest region.
- `medium`: lowest price is 5% to 15% below the United States baseline.
- `low`: lowest price is less than 5% below the United States baseline.
- `none`: lowest price is close to or above the United States baseline.

## Output Limits

- Do not include Android, Web, API, Team, or Enterprise prices in the iOS regional table.
- Do not provide cross-region purchase tutorials.
- Do not judge cross-region subscription feasibility.
- Historical generated artifacts are pruned by the configured retention policy; reports should cite the current `snapshot_id` and source URLs rather than assuming old local files are permanent.
