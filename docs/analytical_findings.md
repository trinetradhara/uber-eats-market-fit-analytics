# Analytical Findings

## Overview

This document consolidates the findings from the 10 SQL analytics modules developed for the Uber Eats Product Analytics project.

The analysis covers:

- Data quality
- Marketplace health
- Customer behavior
- Restaurant performance
- Delivery operations
- Customer experience
- Promotions
- Retention and cohorts
- Unit economics
- Root cause analysis

The dataset contains 500,000 orders across five markets and was synthetically generated for analytical practice. Findings should therefore be interpreted as evidence-based hypotheses rather than conclusions about Uber Eats' real-world business.

---

## Executive Summary

The analysis identifies five major themes:

1. **Marketplace scale does not translate into sustainable unit economics.**
2. **Delivery lateness is a significant customer-experience problem.**
3. **Restaurant preparation time is the largest operational component of delivery duration.**
4. **Customer activation is strong, but the first 30 days represent the most important retention window.**
5. **Promotions are associated with weaker order economics and require incrementality testing before expansion.**

The strongest economic signal is delivery partner cost, while the strongest customer-experience signal is delivery lateness.

---

# 1. Data Quality

### Key findings

- All 16 tables are populated.
- The dataset contains 500,000 orders, 55,000 users, 12,000 restaurants, 12,000 delivery partners and 60 promotions.
- Primary keys are unique across the dataset.
- Foreign-key coverage is 100%, with no orphaned records.
- Order-level financial arithmetic reconciles within the defined tolerance.

### Interpretation

The generated dataset is structurally consistent and suitable for downstream analysis. No major data-quality filters were required before conducting the business analysis.

**Finding type:** Structural validation.

---

# 2. Marketplace Health

### Key findings

### India dominates absolute scale

India contributes approximately **346,818 orders (69.4% of total orders)**.

However, scale does not translate directly into better marketplace economics or engagement quality.

India records approximately **9.54 orders per active user**, compared with **6.81 in Australia**.

Delivery performance remains relatively similar across markets, with delivery rates around 95% and cancellation rates around 4–5%.

### Restaurant demand is broadly distributed

- Top 10 restaurants account for only **1.91% of total orders**.
- **11,852 of 12,000 restaurants** have at least one order.
- Median restaurant volume is approximately **21 orders**.
- 148 restaurants have zero orders.

This suggests the marketplace is not dominated by a small number of restaurants, although some supply remains underutilized.

### Unit economics are negative across markets

Average contribution margin per order is negative in every market.

The observed range is approximately:

- Australia: **-8.12**
- UK: **-8.96**

India has the largest absolute margin loss because of its much larger order volume.

### Interpretation

Marketplace health should not be evaluated using volume alone. India demonstrates substantial scale, but the underlying economics remain negative.

The broad restaurant distribution suggests that the primary marketplace question is less about total supply and more about **local liquidity, discovery and restaurant-level utilization**.

**Finding type:** Descriptive / associational.

---

# 3. Customer Behavior

### Key findings

### Activation and repeat conversion are highly saturated

- Activation rate: **99.32%**
- Activated users: **54,628 / 55,000**
- First-to-second repeat conversion: **98.56%**

This indicates that basic activation and initial repeat behavior are not the major constraints in the generated dataset.

### Customer frequency is relatively strong

- Medium-frequency users (4–9 orders): **51.6%**
- High-frequency users (10+ orders): **38.9%**
- Zero-order users: **0.68%**
- One-order users: **1.43%**

The main opportunity is therefore not simply getting users to place a second order, but increasing frequency and protecting users from disengagement.

### Acquisition channels show limited aggregate variation

Channels cluster around:

- ~99.3% activation
- ~98.5% repeat conversion
- ~8.5–8.75 orders per user

No acquisition channel is decisively superior based on the aggregate analysis.

### Interpretation

The customer base appears highly engaged. Future analysis should focus on **frequency depth, early retention and segment-level churn**, rather than basic activation.

**Finding type:** Descriptive.

---

# 4. Restaurant Performance

### Key findings

Restaurant demand is heavy-tailed:

- 11,852 restaurants receive orders.
- 148 restaurants receive zero orders.
- Top 10 restaurants account for only 1.91% of orders.
- Median restaurant volume is 21 orders.
- Maximum restaurant volume is 1,453 orders.

### Completion performance is relatively stable by cuisine

Completion rates generally cluster around 95%.

FAST_FOOD and CHINESE account for the highest order volumes.

Premium restaurants have:

- Higher AOV: approximately **50.79**
- Slightly worse completion rate: approximately **95.01%**
- Higher cancellation rate: approximately **4.99%**

### Restaurant-level volatility is hidden by aggregate averages

Some lower-volume restaurants show cancellation rates above 20%, despite the overall cancellation rate being approximately 4.6%.

This indicates that aggregate marketplace averages can hide restaurant-specific reliability problems.

### Ratings are incomplete

Only approximately **52.37% of delivered orders receive ratings**.

Restaurants with at least 20 ratings average approximately **4.48**, suggesting that highly rated restaurants may be concentrated among restaurants with stronger review coverage.

### Interpretation

Restaurant supply is broad, but performance varies substantially at the restaurant level.

The next investigation should therefore focus on **restaurant × city × cuisine segments** rather than relying on marketplace-wide averages.

**Finding type:** Descriptive / segmented.

---

# 5. Delivery Operations

### Key findings

### Delivery lateness is widespread

- Average delivery duration: **34.1 minutes**
- Average ETA error: approximately **+3.6 minutes**
- Late-delivery rate: **64.8%**

The high late rate despite a relatively small average ETA error suggests that lateness is structural rather than an occasional operational exception.

### Peak-hour degradation is small at aggregate level

| Metric | Peak | Non-peak |
|---|---:|---:|
| Delivery duration | 34.18 min | 33.88 min |
| Late rate | 65.1% | 64.3% |

The aggregate difference is small.

This does not rule out severe peak-hour problems for individual cities, restaurants or partners.

### Preparation time is the dominant lifecycle component

Average lifecycle decomposition:

- Restaurant preparation: **25.2 min**
- Partner assignment: **6.1 min**
- Post-pickup travel: **4.8 min**

Preparation time is approximately **5× post-pickup travel time**.

### Interpretation

The strongest initial operational hypothesis is **restaurant readiness**, rather than delivery-partner travel.

Reducing preparation time could therefore have greater impact on delivery duration than simply adding delivery capacity.

**Finding type:** Descriptive.

---

# 6. Customer Experience

### Delivery lateness is strongly associated with lower ratings

| Delivery status | Average rating |
|---|---:|
| On-time / early | 4.33 |
| Late | 3.97 |

Difference: **0.36 rating points**

### Support issues are dominated by operational failures

The largest issue categories are:

1. LATE_DELIVERY — **31.0%**
2. MISSING_ITEM — **19.8%**
3. WRONG_ITEM — **13.6%**

Together these represent approximately **64.4% of reported issues**.

### Refunds

Total refunds recorded:

**67,970.90**

across approximately **6,617 transactions**.

Refund analysis should be performed at the order level because a single order can contain multiple issues.

### Interpretation

Customer dissatisfaction is primarily associated with **delivery reliability and fulfillment accuracy**, rather than being dominated by restaurant quality complaints.

Improving operational reliability therefore has the potential to address both customer sentiment and support demand.

**Finding type:** Descriptive / associational.

---

# 7. Promotions

### Key findings

Promotions account for approximately:

- **57,467 redemptions**
- **11.49% of orders**
- Across **60 promotions**

Approximately **60.58% of ordering users** have at least one promoted order.

### Promoted orders have lower basket value

| Order type | Average total paid |
|---|---:|
| Promoted | 25.31 |
| Organic | 28.26 |

Promoted orders are approximately **10.4% smaller**.

### Promoted orders also have weaker contribution margin

| Order type | Contribution margin |
|---|---:|
| Promoted | -11.12 |
| Organic | -8.38 |

Difference: **-2.74 per order**

This represents approximately **32.7% weaker margin** for promoted orders.

### Interpretation

Promotions are associated with weaker economics and smaller baskets.

However, this does **not** establish that promotions cause the weaker economics. Differences may be explained by user selection, basket composition or the underlying characteristics of users who redeem promotions.

Incrementality testing is required before concluding that promotions are value-destructive.

**Finding type:** Descriptive / associational.

---

# 8. Retention & Cohorts

### Key findings

First-to-second delivered-order conversion is approximately:

**98.56%**

However, longer-term retention shows more meaningful separation.

Reported retention:

- 30-day: **49.54%**
- 60-day: **70.87%**
- 90-day: **81.76%**

Median time to second order:

**23 days**

### Interpretation

The first 30 days after activation represent the most useful retention window for further investigation.

The aggregate activation and first-to-second conversion rates are already extremely high, so future retention analysis should focus on:

- Customer frequency
- Market
- Acquisition channel
- First-order experience
- Restaurant category
- Delivery experience
- Short-term repeat windows

**Finding type:** Descriptive.

---

# 9. Unit Economics

### Negative-margin orders dominate

Approximately:

**89.19% of all orders**

have negative contribution margin.

That represents approximately:

**445,938 of 500,000 orders.**

No market achieves positive average unit economics.

### Delivery partner cost is the clearest cost separator

| Order group | Delivery partner cost |
|---|---:|
| Negative margin | 16.85 |
| Non-negative margin | 8.79 |

Negative-margin orders therefore show approximately **91% higher delivery partner cost**.

### Promotions also correlate with weaker economics

Promoted orders:

**-11.12 margin/order**

Organic orders:

**-8.38 margin/order**

### Premium restaurants do not automatically produce positive economics

Premium restaurants generate higher AOV, approximately **50.79**, but still show negative average contribution margin.

### Interpretation

The strongest visible economics problem is **delivery cost**, rather than support or promotion cost alone.

Improving delivery cost efficiency, increasing basket value and reducing discount dependency are therefore the major economic levers suggested by the dataset.

**Finding type:** Descriptive.

---

# 10. Root Cause Analysis

The final RCA module tested three major hypotheses.

## Hypothesis 1: Does lateness hurt customer experience?

**Supported.**

Late orders average:

**3.97 rating**

versus:

**4.33 rating**

for on-time / early orders.

Difference:

**0.36 points**

---

## Hypothesis 2: Does first-order lateness reduce 90-day retention?

**Not supported at aggregate level.**

90-day repeat:

- Late first order: **83.95%**
- On-time first order: **83.98%**

The difference is effectively negligible.

### Important interpretation

This does **not** mean lateness is unimportant.

It means that the generated dataset does not show a meaningful aggregate relationship between first-order lateness and 90-day repeat.

The effect may instead appear in:

- Shorter retention windows
- Lower-frequency users
- Specific cities
- Specific restaurants
- Specific customer cohorts

---

## Hypothesis 3: Are promotions associated with weaker economics?

**Supported as an association.**

Promoted:

**-11.12 margin/order**

Organic:

**-8.38 margin/order**

Difference:

**-2.74/order**

However, this is not a causal estimate.

---

## Hypothesis 4: Where is the operational bottleneck?

**Restaurant preparation time is the strongest initial hypothesis.**

Average lifecycle components:

- Preparation: **25.2 min**
- Assignment: **6.1 min**
- Post-pickup travel: **4.8 min**

Preparation is therefore the dominant component of delivery duration.

---

# Cross-Project Findings

The most important findings across the project are:

1. **89.19% of orders have negative contribution margin.**
2. **Delivery partner cost is the strongest visible separator between profitable and unprofitable orders.**
3. **25.2-minute restaurant preparation time is the largest delivery lifecycle component.**
4. **64.8% of delivered orders are late.**
5. **Late delivery is associated with a 0.36-point lower rating.**
6. **First-order lateness does not materially change aggregate 90-day repeat.**
7. **Customer activation is already extremely high at 99.32%.**
8. **The first 30 days represent the most useful retention window for further investigation.**
9. **Promoted orders have lower AOV and weaker contribution margin than organic orders.**
10. **Restaurant demand is broad, but restaurant-level reliability varies substantially.**
11. **Approximately 64% of reported support issues are related to late, missing or incorrect orders.**
12. **Peak-hour degradation is small at aggregate level, suggesting that restaurant-level or city-level analysis is more informative than marketplace-wide averages.**

---

# Business Problems Identified

## 1. Structural Unprofitability — Highest Severity

The marketplace has negative average contribution margin across every market, with 89.19% of orders generating negative margin.

The largest visible cost difference is delivery partner cost.

**Primary hypothesis:** The current cost structure does not support sustainable order-level economics.

---

## 2. Persistent Delivery Lateness — High Severity

64.8% of delivered orders are late.

Lateness is strongly associated with lower customer ratings and is also one of the largest sources of support demand.

**Primary hypothesis:** Restaurant preparation time is a major contributor to the delivery-time problem.

---

## 3. Early Retention Drop — Medium Severity

Activation and first-to-second conversion are strong, but 30-day retention is substantially lower than aggregate repeat conversion.

**Primary hypothesis:** The largest retention opportunity lies between the first order and longer-term habitual ordering.

---

## 4. Restaurant Preparation Bottleneck — Medium Severity

Preparation accounts for approximately 25.2 minutes of the 34.1-minute average delivery lifecycle.

**Primary hypothesis:** Restaurant readiness and preparation efficiency represent a larger operational opportunity than post-pickup travel.

---

## 5. Promotion Economics — Medium Severity

Promoted orders have approximately 32.7% weaker contribution margin and 10.4% lower basket value than organic orders.

**Primary hypothesis:** Some promotional demand may be non-incremental or concentrated among lower-value orders.

---

# Recommended Next Investigations

The findings suggest five priority areas for deeper analysis.

### 1. Delivery Cost Decomposition

Break delivery partner cost down by:

- City
- Distance
- Delivery partner
- Order size
- Time of day
- Restaurant
- Assignment duration
- Route characteristics

Goal: identify the specific operational drivers behind high delivery cost.

---

### 2. Restaurant Preparation Analysis

Segment preparation time by:

- Restaurant
- Cuisine
- City
- Order volume
- Peak vs. non-peak
- Restaurant price band

Goal: determine whether the 25.2-minute average is driven by a small number of high-delay restaurants or represents a broad structural issue.

---

### 3. Short-Term Retention Analysis

Investigate:

- 7-day repeat
- 14-day repeat
- 30-day repeat
- First-order lateness
- First-order rating
- First restaurant experience
- Customer frequency segment

Goal: identify whether delivery experience affects shorter-term repeat even though aggregate 90-day repeat is unaffected.

---

### 4. Promotion Incrementality

Use:

- Randomized holdouts
- Matched customer cohorts
- Pre/post analysis
- Incremental contribution margin

Goal: determine whether promoted orders create genuinely incremental demand.

---

### 5. City-Level Marketplace Liquidity

Investigate:

- Restaurant availability
- Restaurant utilization
- Order density
- Cancellation rate
- Delivery reliability
- Preparation time
- Customer frequency

Goal: identify local marketplace bottlenecks hidden by country-level averages.

---

# Analytical Limitations

This project uses a synthetic dataset. Therefore, the results should be treated as analytical hypotheses rather than real-world Uber Eats conclusions.

Important limitations include:

- Correlation does not establish causality.
- Promotion-margin differences may reflect selection effects.
- Rating coverage is only approximately 52.37%.
- Aggregate peak-hour metrics may hide city or restaurant-level problems.
- Restaurant preparation time requires restaurant-level segmentation.
- Retention metrics apply to cohorts with appropriate observation windows.
- The generated financial structure produces very high negative-margin prevalence and may not represent real Uber Eats economics.
- The dataset covers approximately 500,000 synthetic orders across five markets and does not capture real-world shocks or edge cases.

---

# Final Takeaway

The analysis suggests that the most important problems are **not customer acquisition or basic activation**.

The strongest opportunities lie in:

**1. Improving delivery cost efficiency**

**2. Reducing restaurant preparation time**

**3. Improving delivery reliability and customer experience**

**4. Protecting early customer retention**

**5. Testing whether promotions create incremental value**

The key analytical lesson is that aggregate marketplace metrics can conceal important segment-level variation. The next stage of analysis should therefore move from **descriptive marketplace-wide metrics toward city, restaurant, customer and order-level drill-downs.**
