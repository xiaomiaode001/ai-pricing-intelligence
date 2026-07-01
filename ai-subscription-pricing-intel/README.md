# ai-subscription-pricing-intel

## 简介 / Overview

`ai-subscription-pricing-intel` 是一个 Codex Skill，用于生成 AI App 全球 iOS 订阅套餐价格信息差报告。它面向日常监测场景，重点展示：**最低 3 地区、美国基准、最高地区、相对美国折扣、相对最高价折扣、汇率复算和 Apple 抽样复核状态**。

`ai-subscription-pricing-intel` is a Codex Skill for generating global iOS subscription price-gap reports for AI apps. It is designed for routine monitoring and highlights: **the lowest 3 regions, US baseline, highest region, discount versus US, discount versus highest price, FX recomputation, and Apple storefront spot-check status**.

## 产品路由 / Product Routes

| Key | Product | App Store ID | Default Detail Plan | Natural-Language Inputs |
|---|---|---|---|---|
| `chatgpt` | ChatGPT | `6448311069` | `ChatGPT Plus 1月` | `GPT套餐监测`, `ChatGPT套餐监测` |
| `claude` | Claude | `6473753684` | `Claude Pro 1月` | `Claude套餐监测` |
| `gemini` | Google Gemini | `6477489729` | `Google AI Pro (5 TB) 1月` | `Gemini套餐监测` |
| `grok` | Grok | `6670324846` | `SuperGrok 1月` | `Grok套餐监测`, `Gork套餐监测` |

套餐名保留 App Store Price 原始标签，不把 Gemini、Claude、ChatGPT、Grok 强行统一成同一套命名。

Plan names are preserved from App Store Price. Gemini, Claude, ChatGPT, and Grok do not need to share the same plan naming style.

## 日常报告格式 / Daily Report Shape

The daily report keeps a compact matrix plus one detailed plan section.

| 套餐 | 周期 | 地区数 | 最低 3 地区 / 价格 / 汇率 | 美国基准 | 最高地区 | 相对美国折扣 | 相对最高折扣 | 信息差等级 | Apple 复核状态 |
|---|---|---:|---|---|---|---:|---:|---|---|
| ChatGPT Plus 1月 | 1M | 33 | 菲律宾 PHP999 / ¥110.86 / FX 0.110870<br>加拿大 CAD24.99 / ¥119.83 / FX 4.790400<br>巴基斯坦 PKR4,900 / ¥119.92 / FX 0.024360 | 美国 $19.99 / ¥136.01 | 哥伦比亚 COP99,900 / ¥197.10 | 18.49% | 43.75% | high | spotcheck_failed |

最低 3 地区会在详情表中展开：

The lowest-3 regions are expanded in the detail table:

| 排名 | 地区 | ISO2 | 原币价格 | source_cny_price | FX | computed_cny_price | FX 状态 | Apple 复核 |
|---:|---|---|---:|---:|---:|---:|---|---|
| 1 | 菲律宾 | PH | PHP999 PHP | ¥110.86 | 0.110870 | ¥110.76 | fx_checked | 复核失败 |
| 2 | 加拿大 | CA | CAD24.99 CAD | ¥119.83 | 4.790400 | ¥119.71 | fx_checked | 已复核 |
| 3 | 巴基斯坦 | PK | PKR4,900 PKR | ¥119.92 | 0.024360 | ¥119.36 | fx_checked | manual_review |

## 来源策略 / Source Policy

| Source | 中文角色 | English Role |
|---|---|---|
| App Store Price | 全地区 iOS IAP 聚合主源 | Primary full-region iOS IAP aggregation source |
| Apple storefront | 低价区、美国基准、最高地区的抽样复核源 | Spot-check source for low-price regions, US baseline, and highest region |
| FX sources | CNY 汇率复算校验源 | CNY recomputation source for verification only |
| Official pricing pages | 产品和套餐命名参考 | Product and plan naming context only |

Rules:

- Keep App Store Price CNY as `source_cny_price`.
- Write Skill recomputation to `computed_cny_price`.
- Do not use `computed_cny_price` or Apple spot-check values to overwrite App Store Price values.
- If sources disagree, show values side by side and mark `conflict`.
- Do not provide cross-region purchase tutorials or feasibility judgments.

## 安装 / Install

From the cloned repository:

```powershell
cd ai-pricing-intelligence/ai-subscription-pricing-intel
```

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -X utf8 scripts/check_environment.py --strict
```

For macOS/Linux, activate the virtual environment with:

```bash
source .venv/bin/activate
```

## 日常监测 / Daily Monitoring

```powershell
python -X utf8 scripts/collect_appstoreprice_intel.py --today --intent-text "GPT套餐监测"
python -X utf8 scripts/collect_appstoreprice_intel.py --today --intent-text "Claude套餐监测"
python -X utf8 scripts/collect_appstoreprice_intel.py --today --intent-text "Gemini套餐监测"
python -X utf8 scripts/collect_appstoreprice_intel.py --today --intent-text "Grok套餐监测"
```

Daily reports are written to `outputs/<snapshot_id>.daily.md`.

## 准确性模式 / Accuracy Modes

| Mode | Behavior |
|---|---|
| `light` | App Store Price + FX recomputation; Apple spot check is manual |
| `balanced` | Default; spot-check lowest 3 regions, United States, and highest region for the detail plan |
| `high` | Spot-check Top 10 low-price regions, United States, and Top 5 high-price regions |

## 校验 / Validation

```powershell
python -X utf8 scripts/check_environment.py --strict
python -X utf8 scripts/check_release_readiness.py --strict
python -X utf8 -m unittest discover -s tests
python -X utf8 -m compileall scripts
```

Optional Codex Skill validation, if you have the Codex skill creator available locally:

```powershell
python -X utf8 "<path-to-skill-creator>/scripts/quick_validate.py" .
```

## 运行数据 / Runtime Data

生成的快照、标准化 JSON/CSV、增强快照、FX 缓存、Apple 抽样结果和 Markdown 报告位于 `data/` 与 `outputs/`，默认被 Git 忽略，仅保留 `.gitkeep`。

Generated snapshots, normalized JSON/CSV, enriched snapshots, FX caches, Apple spot checks, and Markdown reports live in `data/` and `outputs/`. They are ignored by Git except for `.gitkeep`.
