# Business Recommendations

## Objective

Translate the analytical findings into practical product and marketplace actions for Uber Eats.

The recommendations below are based on the observed patterns in the generated dataset. They should be treated as hypotheses and prioritization inputs rather than causal conclusions.

---

## 1. Prioritize restaurant preparation-time reduction

### Evidence

Restaurant preparation is the largest component of the observed delivery-time decomposition:

- Preparation: approximately 25.2 minutes
- Partner assignment: approximately 6.1 minutes
- Post-pickup travel: approximately 4.8 minutes

Preparation therefore represents the strongest initial operational bottleneck.

### Recommendation

Prioritize interventions that reduce restaurant preparation time before focusing heavily on downstream delivery travel.

Potential actions:

- Identify restaurants with consistently high preparation times.
- Compare preparation time across restaurants, cities, and cuisines.
- Introduce restaurant-level preparation-time benchmarks.
- Improve estimated preparation-time inputs used for delivery-partner assignment.
- Investigate whether restaurants with high preparation variance require different operational treatment.

### Success metrics

- Average preparation time
- P75/P90 preparation time
- Preparation-time variance
- Order-to-pickup time
- On-time delivery rate

---

## 2. Investigate late-order customer experience

### Evidence

Late orders have a materially lower average rating:

- Late orders: 3.97
- On-time/early orders: 4.33

This indicates a clear association between delivery lateness and customer sentiment.

However, first-order lateness showed almost no aggregate difference in 90-day repeat behavior:

- Late first orders: approximately 83.95%
- On-time/early first orders: approximately 83.98%

### Recommendation

Treat delivery lateness primarily as a **customer-experience problem**, rather than assuming it is the primary driver of aggregate retention.

Focus on:

- Reducing late deliveries.
- Identifying the operational stages responsible for lateness.
- Segmenting lateness by city, restaurant, cuisine, and demand period.
- Investigating whether severe or repeated lateness has a stronger relationship with retention than a simple late/on-time classification.

### Success metrics

- On-time delivery rate
- Average lateness
- P90 lateness
- Average customer rating
- Rating distribution
- Repeat-order rate among customers experiencing severe/repeated lateness

---

## 3. Re-evaluate promotion economics

### Evidence

Promoted orders showed lower average contribution margin than organic orders:

- Promoted orders: -11.12
- Organic orders: -8.38

This is an observed association and does not establish that promotions directly caused the lower margin.

### Recommendation

Move from broad promotion usage toward more targeted promotion strategies.

Potential approaches:

- Evaluate promotions by customer segment.
- Compare new-user acquisition promotions with retention promotions.
- Measure incremental order frequency rather than promotion-attributed orders alone.
- Identify promotions that generate positive or improving contribution after repeat behavior is considered.
- Review discount depth and minimum-order thresholds.

### Success metrics

- Contribution margin per order
- Incremental orders per promoted user
- Promotion cost per incremental order
- 30/60/90-day retention
- Customer lifetime value
- Repeat purchase rate

---

## 4. Investigate negative-margin orders at the unit-economics level

### Evidence

Delivery-partner cost was substantially higher among negative-margin orders:

- Negative-margin orders: approximately 16.85 average partner cost
- Non-negative-margin orders: approximately 8.79 average partner cost

The generated dataset also contains a very high overall negative-margin share. Because the dataset is synthetic, this should not be interpreted as representative of actual Uber Eats economics.

### Recommendation

Break down negative-margin orders by their underlying cost components instead of treating margin as a single metric.

Investigate:

- Delivery-partner cost
- Customer revenue
- Discounts/promotions
- Delivery distance
- Order value
- Restaurant preparation time
- Market/city
- Time of day
- Customer segment

Prioritize interventions where the economics are both material and operationally controllable.

### Success metrics

- Contribution margin per order
- Negative-margin order share
- Partner cost per order
- Revenue per order
- Promotion cost per order
- Margin by market and order segment

---

## 5. Prioritize market-level investigation rather than using a single marketplace score

### Evidence

The marketplace-health analysis showed differences across markets in:

- Order scale
- Active users
- Delivered orders
- Cancellation rates
- Restaurant supply
- Contribution margin

No single market-level metric should independently determine which market is the strongest or weakest.

### Recommendation

Use a diagnostic market scorecard rather than a single hard-coded ranking.

For each market, evaluate:

1. Demand and engagement
2. Delivery reliability
3. Supply depth
4. Cancellation rate
5. Restaurant concentration
6. Contribution margin
7. Customer retention

Markets with weak performance on multiple dimensions should receive deeper RCA.

### Success metrics

- Orders per active user
- Delivery rate
- Cancellation rate
- Restaurant count
- Contribution margin per order
- Negative-margin share
- Retention

---

## 6. Reduce restaurant concentration risk

### Evidence

The top ten restaurants account for approximately 1.91% of all orders in the generated dataset.

This indicates that overall marketplace volume is not strongly dependent on a very small group of restaurants.

### Recommendation

Continue monitoring restaurant concentration at:

- Market level
- City level
- Cuisine level
- Restaurant level

A market may still have meaningful concentration even when the global marketplace appears diversified.

### Success metrics

- Top-10 restaurant order share
- Top-20 restaurant order share
- Herfindahl-style concentration measure
- Order share by cuisine
- Order share by market

---

# Prioritization Framework

The recommendations can be prioritized using three dimensions:

| Initiative | Customer impact | Economic impact | Priority |
|---|---|---|---|
| Reduce restaurant preparation time | High | High | P1 |
| Improve late-delivery reliability | High | Medium-High | P1 |
| Improve negative-margin unit economics | Medium-High | High | P1 |
| Optimize promotion strategy | Medium | High | P1 |
| Market-level RCA | Medium-High | High | P2 |
| Monitor restaurant concentration | Medium | Medium | P2 |

---

# Recommended Next Experiments

The next analytical step should validate the strongest hypotheses through deeper segmentation rather than immediately implementing broad interventions.

### Experiment 1 — Restaurant preparation

Compare preparation time across:

- Restaurant
- Cuisine
- Market
- Hour of day
- Order volume

Goal: identify whether the 25.2-minute average is driven by a small number of restaurants or represents a broader operational issue.

### Experiment 2 — Severe lateness

Compare customer ratings and repeat behavior across:

- On-time orders
- Mildly late orders
- Moderately late orders
- Severely late orders

Goal: determine whether customer experience and retention deteriorate non-linearly with lateness.

### Experiment 3 — Promotion effectiveness

Compare promoted and organic customers after controlling for:

- New vs existing customer
- Order value
- Market
- Customer activity

Goal: distinguish promotion correlation from potential incremental value.

### Experiment 4 — Negative-margin decomposition

Decompose negative margin by:

- Partner cost
- Promotion cost
- Order value
- Distance
- Preparation time
- Market

Goal: identify the most controllable drivers of loss-making orders.

---

# Decision Principles

1. Do not treat correlation as causation.
2. Segment before making operational recommendations.
3. Prioritize metrics that can be directly influenced by product or operations teams.
4. Evaluate customer experience and unit economics together.
5. Use experiments to validate hypotheses before scaling interventions.
6. Treat synthetic-data findings as portfolio/project evidence rather than real Uber Eats business facts.

---

# Expected Business Impact

If validated, the highest-potential opportunities are:

1. **Reducing restaurant preparation time** to improve delivery reliability and customer experience.
2. **Reducing negative-margin orders** by identifying high-cost order segments.
3. **Improving promotion efficiency** by shifting from broad discounts toward incremental-value-driven targeting.
4. **Reducing severe delivery lateness** to improve customer satisfaction.
5. **Using market and restaurant segmentation** to identify localized operational problems.

The recommended approach is to validate these hypotheses through deeper segmentation and controlled experimentation before making broad marketplace changes.
