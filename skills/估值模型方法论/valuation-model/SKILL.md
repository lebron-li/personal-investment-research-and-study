---
name: 估值模型方法论
description: 估值方法论，涵盖 DCF、DDM、SOTP 等绝对估值，PE-Band、PB-ROE、EV-EBITDA 等相对估值，宏观利率动态 Ke 调整，股息率利差安全边际，财务数据质量修正，估值陷阱识别，以及叙事-数字交叉验证。
category: analysis
---

# Valuation Methodology

## Overview

Systematic corporate valuation framework covering absolute valuation (`DCF / DDM / SOTP`) and relative valuation (`PE / PB / EV-EBITDA`), including sensitivity-analysis methods and a checklist for identifying valuation traps.

## Absolute Valuation Methods

### 1. DCF (Discounted Cash Flow)

**Core formulas**:

```
Enterprise value = Σ FCF_t / (1+WACC)^t + TV / (1+WACC)^n
Equity value = enterprise value - net debt
Per-share value = equity value / total shares outstanding
```

**Detailed steps**:

#### Step 1: Forecast free cash flow (usually 5 years)

```
FCFF = EBIT × (1-tax rate) + depreciation & amortization - capex - increase in working capital

Simplified version:
FCFF ≈ operating cash flow - capex
```

| Year | Revenue (100m RMB) | EBIT (100m RMB) | FCFF (100m RMB) | Growth |
|------|---------|---------|---------|------|
| 2026E | 120 | 24 | 18 | +15% |
| 2027E | 138 | 28 | 21 | +15% |
| 2028E | 155 | 31 | 24 | +12% |
| 2029E | 170 | 34 | 26 | +10% |
| 2030E | 182 | 36 | 28 | +7% |

#### Step 2: Calculate WACC

```
WACC = E/(D+E) × Ke + D/(D+E) × Kd × (1-T)

Ke (cost of equity) = Rf + β × (Rm - Rf)
  - Rf: 10-year government bond yield (about 2.5% for China A-shares)
  - β: industry average or company beta (1.0-1.5)
  - Rm-Rf: equity risk premium (about 5-7% for China A-shares)

Kd: cost of debt (loan rate, about 4-5%)
T: income tax rate (25%)
```

**Reference WACC ranges for China A-shares**:

| Industry | WACC Range | Reference β |
|------|---------|------|
| Consumer | 8-10% | 0.8-1.0 |
| Technology | 10-13% | 1.2-1.5 |
| Financials | 7-9% | 1.0-1.2 |
| Cyclicals | 9-12% | 1.0-1.4 |
| Utilities | 6-8% | 0.5-0.8 |

#### Step 2.5: Macro-Regime-Adjusted Ke

**Ke is not a constant — it is a function of the macro environment.**

```
Base Ke = Rf + β × ERP
```

In a rate-cutting cycle:
- Rf falls more than ERP rises (typically)
- Net effect: Ke trends down
- Consequence: The "fair PB" implied by PB-ROE is a moving target

**Dynamic Ke Scenario Table (China A-shares)**:

| Regime | Rf | ERP | Bank Ke (β=1.1) | Implied Fair PB (ROE=10%,g=3%) |
|--------|----|----|-----------|--------------------------|
| Tightening (2022-23) | 2.8% | 7% | 10.5% | 1.00x |
| Neutral | 2.5% | 6.5% | 9.65% | 1.17x |
| Easing (current) | 1.6% | 7% | 9.3% | 1.27x |
| Deep easing | 1.2% | 6% | 7.8% | 1.67x |

**Key insight**: In a rate-easing cycle, a static-Ke DCF will systematically undervalue. Always run a **three-scenario Ke sensitivity**:
- **High Ke**: Current ERP, no rate pass-through
- **Base Ke**: Rf updated to latest, ERP unchanged
- **Low Ke**: Rf down + ERP compression

**Validation check**: If PB remains below all three scenarios, the market is pricing something beyond rate expectations — likely asset quality fears or hidden losses.

**Critical detail**: The 10Y government bond yield in China has fallen from ~2.8% (2022) to ~1.6% (2025). If your model still uses Rf=2.5%, you are overstating Ke by ~90bp and systematically undervaluing.

#### Step 3: Terminal Value

```
Perpetual-growth method: TV = FCF_n × (1+g) / (WACC - g)
  - g: perpetual growth rate (usually 2-3%, should not exceed GDP growth)

Exit-multiple method: TV = EBITDA_n × EV/EBITDA multiple
  - Reference the industry average or historical median
```

#### Step 4: Sensitivity Analysis

```markdown
### DCF Sensitivity Analysis (per-share value, RMB)

| WACC \ g | 2.0% | 2.5% | 3.0% |
|----------|------|------|------|
| 9.0% | 32.5 | 35.8 | 40.2 |
| 9.5% | 28.3 | 30.8 | 34.0 |
| 10.0% | 24.8 | 26.7 | 29.1 |
| 10.5% | 22.0 | 23.5 | 25.3 |
| 11.0% | 19.6 | 20.8 | 22.2 |
```

### 2. DDM (Dividend Discount Model)

**Applicable to**: high-dividend stocks (banks, utilities, mature consumer companies).

```
Two-stage DDM:
P = Σ D_t / (1+Ke)^t + D_n × (1+g) / [(Ke-g) × (1+Ke)^n]

Gordon model (single stage):
P = D_1 / (Ke - g)
```

**Applicability checklist**:
- [x] Has paid dividends continuously for more than 3 years
- [x] Stable payout ratio (>30%)
- [x] Strong earnings predictability
- [ ] Usually not suitable for high-growth stocks (no dividends / low payout)

### DDM Extension: Yield Spread as Safety Margin

Beyond the theoretical price, the **spread between dividend yield and risk-free rate** is a critical second dimension — especially in "asset famine" environments like China's current market.

**Framework**:

```
Dividend Yield = DPS / Price
Yield Spread = Dividend Yield - 10Y Government Bond Yield
```

**Interpretation matrix**:

| Yield Spread | Signal | Action Implication |
|-------------|--------|-------------------|
| > 400bp | Extreme undervaluation OR dividend cut fear | Investigate dividend sustainability |
| 200-400bp | Attractive, bond-like defense active | Accumulate zone if dividend is stable |
| 100-200bp | Fair, moderate safety margin | Hold, no urgency |
| < 100bp | No bond-like defense | Price relies entirely on growth expectation |

**Critical caveat — the "Dividend Cut Trap"**:
A widening yield spread can mean TWO opposite things:
- **(A) Price is cheap** → buy signal ✅
- **(B) Market expects dividend to be cut** → warning signal ⚠️

Distinguishing A from B requires checking:
- **Payout ratio trend**: Rising → dividend stress?
- **Free cash flow / dividend ratio**: Consistently > 1.5x?
- **ROE trend**: Declining ROE → dividend sustainability threatened

**China-specific — "Bond-Substitution" demand**:
Insurance funds and pension funds dominate incremental demand for high-dividend bank stocks. Their liability cost is ~3-4%, making a 5%+ dividend yield structurally attractive **regardless of short-term price action**. This creates a valuation floor that pure PB-ROE theory does not capture — the floor is determined by institutional cost of capital, not by theoretical fair value.

**When this defense breaks**:
- Dividend ratio is cut (payout drops from 30% to 20%)
- ROE decline forces dividend reduction
- Regulatory pressure to retain capital

### 3. SOTP (Sum of the Parts)

**Applicable to**: diversified conglomerates.

```
Group value = Σ valuation of each business segment + net cash - holding-company discount

Example (a group company):
| Segment | Revenue (100m RMB) | Valuation Method | Valuation (100m RMB) |
|------|---------|---------|---------|
| Baijiu | 80 | 30x PE | 600 |
| Real estate | 50 | 0.6x PB | 120 |
| Financials | 30 | 1.0x PB | 200 |
| Total | | | 920 |
| Holding-company discount | | -15% | -138 |
| Group valuation | | | 782 |
```

## Relative Valuation Methods

### 1. PE Band

```
Historical PE percentile analysis:
- Take the past 5 years of PE_TTM time series
- Compute the 10% / 25% / 50% / 75% / 90% percentiles
- Judge overvaluation / undervaluation from the current PE percentile

| Percentile | PE | Implied Price | Interpretation |
|------|-----|---------|------|
| 90% | 35x | 52.5 | Severely overvalued |
| 75% | 28x | 42.0 | Rich |
| 50% | 22x | 33.0 | Fair |
| 25% | 16x | 24.0 | Cheap |
| 10% | 12x | 18.0 | Severely undervalued |
| Current | 18x | 27.0 | Cheap (30th percentile) |
```

### 2. PB-ROE Matrix

```
Theoretical relationship: PB = (ROE - g) / (Ke - g)
Practical use: plot companies in the industry on a PB vs ROE scatter chart

| Quadrant | PB | ROE | Interpretation |
|------|-----|-----|------|
| Lower right | Low PB | High ROE | Undervalued (best buy zone) |
| Upper right | High PB | High ROE | Fair (quality premium) |
| Lower left | Low PB | Low ROE | Value trap or distressed turnaround |
| Upper left | High PB | Low ROE | Overvalued (avoid) |
```

### 3. EV/EBITDA

```
EV = market cap + net debt (interest-bearing debt - cash)
EBITDA = operating profit + depreciation + amortization

Advantages:
- Removes capital-structure differences (vs PE)
- Removes depreciation-policy differences
- Suitable for asset-heavy industries (telecom / energy / infrastructure)

Reference EV/EBITDA ranges by China A-share industry:
| Industry | Median | Undervalued | Overvalued |
|------|--------|------|------|
| Consumer | 15-20x | <12x | >25x |
| Technology | 12-18x | <10x | >22x |
| Energy | 6-10x | <5x | >12x |
| Utilities | 8-12x | <6x | >15x |
```

## Valuation-Trap Detection

### Top 11 Valuation Traps

| # | Trap | Detection Method | Typical Example |
|---|------|---------|---------|
| 1 | Low-PE cyclical at the peak | PE is lowest when earnings are highest and about to fall | Coal at 5x PE in 2021 was the top |
| 2 | High-PE growth can be justified | `PEG < 1` means the growth rate supports the valuation | 30x PE + 40% growth = PEG 0.75 |
| 3 | Low-PB value destruction | Sustained `ROE < Ke` means shareholder value is being destroyed | Long-term loss-making asset-heavy company |
| 4 | Goodwill bomb | Goodwill / net assets >30% implies impairment risk | Underperforming acquisition after paying a high premium |
| 5 | Accounts-receivable trap | Rising receivables / revenue ratio = poor revenue quality | Government receivables + high customer concentration |
| 6 | Capitalization trap | Capitalizing R&D / interest flatters profit | PE doubles after true expensing |
| 7 | One-off gains | Large gap between recurring net profit and reported net profit | Asset sales / government subsidies boost earnings |
| 8 | Share dilution | Stock options / convertible bonds reduce EPS | PE should be based on diluted EPS |
| 9 | Related-party transactions | Buy cheap from related parties / sell high to them | Profit shifted outside the listed entity |
| 10 | FX swings | High overseas-revenue share means large currency sensitivity | RMB appreciation erodes exporter profits |
| 11 | Provisioning-smoothing trap | Banks/insurers: high provisions mask true earnings power. When provisions reverse, ROE jumps sharply. | Check: provision coverage ratio trend + NPL formation rate + compare "normalized credit cost" vs current |

## Financial Data Quality Adjustment

**Before plugging numbers into any valuation model, verify the inputs are real.**

### Bank-Specific: Adjusted ROE

```
Adjusted ROE = Reported ROE + (Excess Provision / Equity) × (1 - Tax Rate)

Where:
  Excess Provision = Actual Provisions - Normalized Credit Cost × Loan Book
  Normalized Credit Cost = 5-year average credit cost through the cycle
```

**Quick test**:
- Provision coverage ratio > 300% AND NPL formation rate declining
  → Likely over-provisioned → Adjusted ROE > Reported ROE
- Provision coverage ratio < 200% AND NPL formation rate rising
  → Likely under-provisioned → Adjusted ROE < Reported ROE

### General Data Quality Red Flags

| Red Flag | What It Hides | How to Adjust |
|----------|-------------|---------------|
| Provision/revenue ratio rising sharply | Future profit release or hidden losses | Compare with industry peers, check NPL migration |
| Capitalized R&D / total R&D > 50% | Overstated profit | Recompute PE with full expensing |
| Non-recurring profit / net profit > 20% | Core business weaker than it looks | Use recurring EPS for PE calculation |
| Receivables growth > revenue growth × 1.5 | Revenue quality deteriorating | Discount receivables in BV |
| Goodwill / net assets > 30% | Impairment time bomb | Stress-test BV with goodwill write-off |
| Operating cash flow / net profit consistently < 0.8 | Profit not converting to cash | Use operating cash flow instead of earnings |

## Analysis Framework

### Valuation-Method Selection Decision Tree

```
What type of company is it?
├── Mature and stable (consumer / utilities / banks)
│   ├── High dividend -> DDM
│   └── Low dividend -> DCF + PE Band
├── High growth (tech / pharma / new energy)
│   └── DCF (high-growth phase) + PEG + PS
├── Cyclical (coal / steel / nonferrous)
│   └── PB + EV/EBITDA (avoid PE)
├── Diversified conglomerate
│   └── SOTP
└── Loss-making company
    └── PS (price-to-sales) + EV/Sales
```

### Cross-Validation

```
Use at least 2 valuation methods and take the middle value:
1. DCF -> intrinsic value
2. Comparable PE -> market pricing
3. If the difference >30% -> check whether assumptions are reasonable
```

## Meta-Check: Narrative vs Numbers

Every valuation model produces a number. But every number is backed by a narrative. Before finalizing any valuation, validate the narrative that supports it.

### The Three-Condition Test

Every bullish valuation case rests on 2-4 key assumptions. List them explicitly:

| Condition | State Today | Confidence | If Wrong, Target Moves To |
|-----------|------------|-----------|--------------------------|
| [e.g., Rate cuts continue] | ✅ Direction clear | Medium | Lower by 15-20% |
| [e.g., NPL formation peaks] | ❓ Unclear | Low | Lower by 30%+ |
| [e.g., Dividend ratio holds] | ❓ Depends on NPL | Low-Medium | Lower by 10-15% |

**Rule**: For each condition, estimate the valuation impact if it breaks. If the weakest link carries a 30%+ downside, reduce position sizing accordingly.

### The "Market Disagreement" Test

If your fair value is **2x or more** above the market price, do not assume the market is stupid. Ask:

1. "What does the market know that I don't?" — Construct the explicit bear case
2. "Can I articulate the bear case better than a bear?" — If you can't, you don't understand the risk
3. "Does my thesis survive the worst plausible scenario?" — Stress-test with the bear's assumptions

**When to trust the discount**: The market's discount is a genuine mispricing when:
- The bear case is visible but overblown (measurable, temporary, fixable)
- You have an information edge (earlier recognition of turning point)
- The catalyst timeline is within your holding period

**When to distrust the discount**: The discount is rational when:
- The bear case is structural (industry decline, business model obsolescence)
- The discount has persisted for years without catalyst
- Insiders are selling, not buying

### Position Sizing from Valuation Confidence

```
Max position size (%) = Base allocation × Confidence in weakest link

Example:
- Base allocation for a high-conviction idea: 15%
- Weakest link confidence: 60% (NPL peak timing)
- Max position: 15% × 60% = 9%
```

**Never size a position larger than your confidence in the weakest assumption.**

## Output Format

```markdown
## Valuation Analysis: [Company Name / Code]

### Valuation Summary
| Method | Per-Share Value | Weight | Notes |
|------|---------|------|------|
| DCF | ¥32.5 | 50% | WACC=10%, g=2.5% |
| Comparable PE | ¥28.0 | 30% | Industry average 22x, EPS=1.27 |
| PB-ROE | ¥30.0 | 20% | Fair PB=2.5x |
| **Composite Target Price** | **¥30.8** | | Current price 25.0, upside +23% |

### Sensitivity Analysis
[WACC vs growth-rate matrix]

### Valuation-Trap Check
- [x] Is PE a falsely low cyclical peak? -> No
- [x] Goodwill / net asset ratio -> 12%, safe
- [x] Receivables / revenue trend -> Stable, not deteriorating
- [ ] Gap in recurring net profit -> 15% difference, subsidy dependence worth attention

### Investment Rating: Buy
Target price ¥30.8, current price ¥25.0, upside 23%
```

## Notes

1. **DCF is highly sensitive to assumptions**: a 1% change in WACC can move valuation by 20%+, so sensitivity analysis is mandatory. In rate-cutting cycles, always run the macro-regime-adjusted Ke scenarios (Step 2.5).
2. **Ke is a moving target**: update Rf to the latest 10Y bond yield before every valuation. Do not use stale risk-free rates.
3. **Comparable companies must truly be comparable**: same industry + same scale + same stage; do not apply leader PE multiples to small companies
4. **China A-share valuation system is unique**: shell value / liquidity premium / policy premium / asset-famine dynamics mean US-equity standards cannot be copied directly
5. **Valuation is not a target price**: markets can remain irrational for a long time, and valuation is an anchor, not a trading signal
6. **Financial data is not transparent**: verify inputs before modeling (see Financial Data Quality Adjustment). Banks' ROE can be significantly distorted by provisioning policy.
7. **Yield spread is a second dimension**: DDM price alone misses the bond-substitution demand that creates valuation floors in asset-famine markets
8. **Special handling for cyclicals**: use normalized earnings (mid-cycle earnings), not current earnings
9. **Narrative drives numbers**: every DCF output is only as good as its assumptions. Run the Three-Condition Test and Market Disagreement Test before finalizing any valuation.
10. **Not suitable for cryptocurrencies**: traditional valuation frameworks do not apply to BTC / ETH; use on-chain metrics instead (see `onchain-analysis`)
