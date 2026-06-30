# FX Source Policy

Use this policy when recalculating App Store Price CNY values from local iOS prices.

## Source Priority

1. Frankfurter API.
2. ECB reference rates when the currency is supported.
3. ExchangeRate-API open access fallback.
4. `manual_fx_snapshot` final fallback.

## Required Fields

Every FX row must include:

- `fx_source`
- `fx_rate_date`
- `fx_base_currency`
- `fx_target_currency`
- `fx_rate_to_cny`
- `fx_status`
- `rate_is_latest_business_day`

## Business-Day Rules

- Weekend or holiday rates may use the latest available business-day rate.
- When the latest available rate date is before the request date, set `rate_is_latest_business_day` to `true`.
- When a same-day rate is available, set `rate_is_latest_business_day` to `false`.
- If no rate can be found for a currency, set `fx_status` to `missing` and do not silently drop the currency.

## Recalculation Rules

- Calculate `computed_cny_price = parsed_local_amount * fx_rate_to_cny`.
- Keep App Store Price's `source_cny_price`; never overwrite it.
- Calculate `cny_delta = computed_cny_price - source_cny_price`.
- Calculate `cny_delta_pct = cny_delta / source_cny_price * 100`.
- If `abs(cny_delta_pct) > 1.5`, set `fx_verification_status` to `fx_mismatch`; otherwise set it to `fx_checked`.
