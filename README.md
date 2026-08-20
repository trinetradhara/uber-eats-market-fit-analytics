# Uber Eats Marketplace & Product Analytics

An end-to-end SQL analytics project analyzing a synthetic Uber Eats marketplace across customers, restaurants, deliveries, promotions, retention, customer experience, and unit economics.

The project combines marketplace analytics with product-oriented root cause analysis to identify operational and economic opportunities.

---

## Business Objective

The objective is to understand marketplace health and identify the major drivers of:

- Customer engagement and retention
- Delivery reliability
- Restaurant performance
- Customer satisfaction
- Promotion effectiveness
- Contribution margin
- Negative-margin orders

The analysis moves from descriptive marketplace diagnostics toward evidence-based root cause analysis and business recommendations.

---

## Dataset

The project uses a synthetic Uber Eats-style dataset representing:

- 500,000 orders
- 5 markets
- Approximately 8–12 months of marketplace activity
- Customers
- Restaurants
- Orders
- Delivery events
- Ratings
- Issues and refunds
- Promotions and redemptions
- Order-level financials

The dataset was generated specifically for analytics practice and portfolio demonstration. It should not be interpreted as real Uber Eats operational data.

---

## Analytical Framework

The analysis was structured into the following modules:

### 1. Data Quality & Schema

Validated dataset structure, relationships, completeness, and analytical assumptions.

### 2. Marketplace Health

Analyzed:

- Order volume
- Active users
- Orders per active user
- Delivery and cancellation rates
- Restaurant supply
- Marketplace concentration
- Contribution margin

### 3. Customer Behavior

Analyzed customer ordering patterns and engagement across the marketplace.

### 4. Restaurant Performance

Evaluated restaurant-level order volume and marketplace contribution.

### 5. Delivery Operations

Decomposed delivery time across operational stages:

- Restaurant preparation
- Partner assignment
- Post-pickup travel

### 6. Customer Experience

Analyzed:

- Ratings
- Delivery lateness
- Customer issues
- Refund behavior

### 7. Promotions

Evaluated promotion usage and its relationship with order economics.

### 8. Retention & Cohorts

Analyzed customer retention and repeat behavior using cohort-based metrics.

### 9. Unit Economics

Investigated contribution margin and the characteristics of negative-margin orders.

### 10. Root Cause Analysis

Combined customer experience, operational, promotional, and financial evidence to identify the strongest business hypotheses.

---

## Key Findings

### Delivery reliability affects customer experience

Late orders received lower average ratings:

| Order Type | Average Rating |
|---|---:|
| Late | 3.97 |
| On-time / early | 4.33 |

However, first-order lateness showed almost no aggregate difference in 90-day repeat behavior in the analyzed sample.

This suggests that delivery lateness is clearly associated with customer sentiment, but should not automatically be treated as the primary aggregate retention driver.

---

### Restaurant preparation is the strongest operational bottleneck

Observed delivery-time decomposition:

| Stage | Approx. Time |
|---|---:|
| Restaurant preparation | 25.2 min |
| Partner assignment | 6.1 min |
| Post-pickup travel | 4.8 min |

Restaurant preparation represents the largest component of the observed delivery process.

This makes restaurant-level preparation-time segmentation an important next investigation.

---

### Promotions are associated with weaker unit economics

Average contribution margin:

| Order Type | Contribution Margin |
|---|---:|
| Promoted | -11.12 |
| Organic | -8.38 |

This is an observed association, not a causal estimate.

The next step should be to evaluate promotion effectiveness using customer segmentation and incremental behavior.

---

### Delivery-partner cost is higher among negative-margin orders

Average delivery-partner cost:

| Order Group | Partner Cost |
|---|---:|
| Negative-margin orders | 16.85 |
| Non-negative-margin orders | 8.79 |

This indicates that delivery-partner cost is an important candidate driver of poor order-level economics.

---

### Marketplace concentration is relatively low

The top ten restaurants account for approximately 1.91% of all orders in the generated dataset.

This suggests that overall marketplace volume is not highly dependent on a very small group of restaurants.

---

## Business Recommendations

The analysis leads to five major recommendation areas:

### P1 — Reduce restaurant preparation time

Identify restaurants, cuisines, and markets with unusually high preparation times and reduce operational bottlenecks.

### P1 — Improve delivery reliability

Focus on reducing severe and repeated lateness while measuring the resulting impact on customer experience.

### P1 — Improve negative-margin economics

Decompose loss-making orders by partner cost, promotion cost, order value, distance, and market to identify controllable cost drivers.

### P1 — Improve promotion efficiency

Move from broad discounting toward targeted promotions based on incremental customer value and retention.

### P2 — Use market-level segmentation

Prioritize markets based on multiple dimensions including demand, reliability, supply, retention, cancellation rate, and contribution margin.

---

## Technical Stack

- SQL
- DuckDB
- Python
- CSV
- Git
- GitHub
- Cohort analysis
- Window functions
- CTEs
- Aggregations
- Root cause analysis
- Product analytics
- Marketplace analytics
- Unit economics

---

## Repository Structure

```text
data/        → Synthetic raw datasets
docs/        → Analytical findings and recommendations
notebooks/   → Exploratory analysis
sql/         → Analytical SQL modules
src/         → Data generation / supporting code
