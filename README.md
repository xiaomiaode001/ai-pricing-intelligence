# AI Pricing Intelligence

[![Validate](https://github.com/xiaomiaode001/ai-pricing-intelligence/actions/workflows/validate.yml/badge.svg)](https://github.com/xiaomiaode001/ai-pricing-intelligence/actions/workflows/validate.yml)

## 项目说明 / Project Overview

AI Pricing Intelligence 是一个面向 Codex 的 Skill 项目，用于监测 ChatGPT、Claude、Gemini、Grok 等 AI 产品在全球不同 iOS App Store 地区的订阅套餐价格差异。它的核心目标是回答一个日常情报问题：**现在某个 AI 套餐哪里最便宜、美国基准价是多少、最高价在哪里、价差空间有多大**。

AI Pricing Intelligence is a Codex Skill for monitoring global iOS in-app subscription price gaps for AI products such as ChatGPT, Claude, Gemini, and Grok. Its core purpose is to answer a practical daily intelligence question: **which region is currently cheapest, what is the US baseline, where is the highest price, and how large is the price gap**.

The canonical Skill package lives in [`ai-subscription-pricing-intel/`](ai-subscription-pricing-intel/).

## 核心特点 / Key Highlights

| 中文 | English |
|---|---|
| 按产品输入即可生成全球 iOS 套餐监测短报 | Generate a global iOS subscription report from a product-level prompt |
| 固定输出最低 3 地区、美国基准、最高地区和价差折扣 | Always show the lowest 3 regions, US baseline, highest region, and discount gap |
| App Store Price 作为全地区聚合主源 | Use App Store Price as the primary full-region aggregation source |
| 汇率复算只用于校验 CNY，不覆盖源价格 | Recompute CNY with FX rates for verification without overwriting source prices |
| Apple storefront 只做抽样复核，冲突并列展示 | Use Apple storefront spot checks only, showing conflicts side by side |
| 默认生成日常短报，也支持完整 11 模块报告 | Produce daily short reports by default, with optional full 11-module reports |

## 适用场景 / Use Cases

Use this Skill when you want a clear daily report such as:

- `GPT套餐监测`
- `Claude套餐监测`
- `Gemini套餐监测`
- `Grok套餐监测` or `Gork套餐监测`

本项目只聚焦 iOS IAP 地区价格信息差，不覆盖 Android、Web、API、Team、Enterprise 价格，也不提供跨区购买教程或可行性判断。

This project focuses only on iOS IAP regional price gaps. It does not cover Android, Web, API, Team, or Enterprise prices, and it does not provide cross-region purchase instructions or feasibility judgments.

## 核心输出维度 / Core Output Dimensions

Every daily report uses the same base dimensions, so different products remain comparable even when their plan names differ.

| 维度 / Dimension | 含义 / What It Shows |
|---|---|
| 套餐 / Plan | App Store Price 原始套餐名，例如 `ChatGPT Plus 1月` 或 `Claude Pro - Monthly 1月` |
| 周期 / Billing Cycle | 月付、年付或 usage-style 套餐 |
| 地区数 / Region Count | 当前套餐采集到的 App Store 地区数量 |
| 最低 3 地区 / 价格 / 汇率 | Three cheapest regions with local price, `source_cny_price`, FX rate, and `computed_cny_price` |
| 美国基准 / US Baseline | United States price as a common comparison baseline |
| 最高地区 / Highest Region | Highest captured regional price |
| 相对美国折扣 / Discount vs US | Lowest region discount versus the US baseline |
| 相对最高折扣 / Discount vs Highest | Lowest region discount versus the highest region |
| 信息差等级 / Intelligence Level | `high`, `medium`, `low`, or `none` |
| Apple 复核状态 / Apple Spot Check | Apple storefront spot-check status for the detailed plan |

## 示例快照 / Example Snapshot

以下样例来自 2026-06-30 生成的 ChatGPT 日常短报。价格会随时间变化；该表用于展示输出格式，不代表永久价格。

The sample below comes from a ChatGPT daily report generated on 2026-06-30. Prices change over time; this is an output-shape example, not a permanent price claim.

| Product | Focus Plan | Lowest Region | US Baseline | Highest Region | Gap vs Highest | Info Level |
|---|---|---|---|---|---:|---|
| ChatGPT | ChatGPT Plus 1月 | 菲律宾 / PHP999 / ¥110.86 | 美国 / $19.99 / ¥136.01 | 哥伦比亚 / COP99,900 / ¥197.10 | 43.75% | high |

### 最低 3 地区示例 / Lowest 3 Regions Example

| Rank | Region | Local Price | source_cny_price | FX Rate to CNY | computed_cny_price | FX Status |
|---:|---|---:|---:|---:|---:|---|
| 1 | 菲律宾 | PHP999 PHP | ¥110.86 | 0.110870 | ¥110.76 | fx_checked |
| 2 | 加拿大 | CAD24.99 CAD | ¥119.83 | 4.790400 | ¥119.71 | fx_checked |
| 3 | 巴基斯坦 | PKR4,900 PKR | ¥119.92 | 0.024360 | ¥119.36 | fx_checked |

### 套餐矩阵示例 / Product Matrix Example

| 套餐 | 周期 | 地区数 | 最低 3 地区 / 价格 / 汇率 | 美国基准 | 最高地区 | 相对美国折扣 | 相对最高折扣 | 信息差等级 |
|---|---|---:|---|---|---|---:|---:|---|
| ChatGPT Plus 1月 | 1M | 33 | 菲律宾 PHP999 / ¥110.86 / FX 0.110870<br>加拿大 CAD24.99 / ¥119.83 / FX 4.790400<br>巴基斯坦 PKR4,900 / ¥119.92 / FX 0.024360 | 美国 $19.99 / ¥136.01 | 哥伦比亚 COP99,900 / ¥197.10 | 18.49% | 43.75% | high |
| ChatGPT Go 1月 | 1M | 33 | 印尼 IDR75,000 / ¥28.53 / FX 0.000380<br>印度 INR399 / ¥28.73 / FX 0.072020<br>菲律宾 PHP300 / ¥33.29 / FX 0.110870 | 美国 $8 / ¥54.43 | 挪威 NOK99 / ¥67.81 | 47.58% | 57.93% | high |

## 情报流程 / Intelligence Flow

```mermaid
flowchart LR
    A["产品输入<br/>GPT / Claude / Gemini / Grok"] --> B["App Store Price 快照<br/>global iOS IAP aggregation"]
    B --> C["套餐与地区标准化<br/>plan matrix + regional rows"]
    C --> D["汇率复算<br/>computed_cny_price"]
    C --> E["Apple 抽样复核<br/>lowest 3 + US + highest"]
    D --> F["日常短报<br/>lowest regions, US baseline, highest region"]
    E --> F
    F --> G["信息差判断<br/>discount and intelligence level"]
```

## 来源分工 / Source Roles

| Source | Role | Overwrite Rule |
|---|---|---|
| App Store Price | 全地区 iOS IAP 聚合主源 / Primary full-region iOS IAP aggregation source | Kept as `source_cny_price`; never overwritten |
| Apple storefront | 重点地区抽样复核 / Spot-check source for selected regions | Shown side by side; never overwrites App Store Price |
| FX sources | CNY 复算校验 / CNY recomputation for verification | Writes `computed_cny_price`; never overwrites `source_cny_price` |
| Official pricing pages | 产品与套餐命名参考 / Product and plan naming context | Not used to override iOS regional prices |

## 支持产品 / Supported Products

| Key | Product | Provider | App Store ID | Default Detail Plan |
|---|---|---|---|---|
| `chatgpt` | ChatGPT | OpenAI | `6448311069` | `ChatGPT Plus 1月` |
| `claude` | Claude | Anthropic | `6473753684` | `Claude Pro 1月` |
| `gemini` | Google Gemini | Google | `6477489729` | `Google AI Pro (5 TB) 1月` |
| `grok` | Grok | xAI | `6670324846` | `SuperGrok 1月` |

## 仓库结构 / Repository Layout

| Path | Purpose |
|---|---|
| `ai-subscription-pricing-intel/` | Canonical Codex Skill package |
| `.github/` | GitHub Actions, issue templates, and PR template |
| `.agents/` | Project-local agent metadata |
| `README.md` | Repository overview |
| `LICENSE` | MIT license |
| `CHANGELOG.md` | Release notes |
| `CONTRIBUTING.md` | Contribution and validation guide |
| `SECURITY.md` | Security and data-handling policy |
| `RELEASE_CHECKLIST.md` | Pre-publish checklist |

## 快速开始 / Quick Start

Clone the repository first, then enter the Skill package directory. Use Python 3.10+; Python 3.12 is recommended. Run commands with UTF-8 enabled.

```powershell
git clone https://github.com/xiaomiaode001/ai-pricing-intelligence.git
cd ai-pricing-intelligence/ai-subscription-pricing-intel
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -X utf8 scripts/check_environment.py --strict
```

For macOS/Linux:

```bash
git clone https://github.com/xiaomiaode001/ai-pricing-intelligence.git
cd ai-pricing-intelligence/ai-subscription-pricing-intel
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -X utf8 scripts/check_environment.py --strict
```

## 日常监测 / Daily Monitoring

```powershell
python -X utf8 scripts/collect_appstoreprice_intel.py --today --intent-text "GPT套餐监测"
python -X utf8 scripts/collect_appstoreprice_intel.py --today --intent-text "Claude套餐监测"
python -X utf8 scripts/collect_appstoreprice_intel.py --today --intent-text "Gemini套餐监测"
python -X utf8 scripts/collect_appstoreprice_intel.py --today --intent-text "Grok套餐监测"
```

Daily reports are written to `ai-subscription-pricing-intel/outputs/`.

## 校验 / Validation

```powershell
cd ai-pricing-intelligence/ai-subscription-pricing-intel
python -X utf8 scripts/check_environment.py --strict
python -X utf8 scripts/check_release_readiness.py --strict
python -X utf8 -m unittest discover -s tests
python -X utf8 -m compileall scripts
```

Optional Codex Skill validation, if you have the Codex skill creator available locally:

```powershell
python -X utf8 "<path-to-skill-creator>/scripts/quick_validate.py" .
```

## 数据安全 / Data Safety

生成的快照、标准化文件、FX 缓存、Apple 抽样结果、Markdown 报告、`.env`、凭证、cookies 和账号相关数据默认不进入 Git。

Generated snapshots, normalized files, FX caches, Apple spot-check JSON, Markdown reports, `.env` files, credentials, cookies, and account-specific data are ignored by Git.

The project intentionally keeps only `.gitkeep` files inside runtime directories. Historical generated artifacts are pruned by retention policy, with at least the latest two snapshots per product retained for comparison.
