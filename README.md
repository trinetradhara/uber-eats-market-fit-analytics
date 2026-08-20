# Synthetic Uber Eats Product Analytics Dataset

This project will generate a reproducible relational dataset for SQL and Product Analytics analysis of marketplace scale, retention, restaurant supply, delivery reliability, promotions, and contribution margin across India, USA, Australia, the UK, and Japan.

The generator is intentionally scaffolded first. It does **not** currently generate the target 500,000 orders or write CSV datasets.

## Objective

Support analysis of why Uber Eats achieved sustainable scale in some markets but may have failed to establish itself in India. The data-generating process introduces market, city, user, restaurant, partner, and operational variation without hard-coding a market ranking or conclusion.

## Project Structure

- `src/config.py`: centralized scale, dates, seed, market priors, and edge-case rates
- `src/rng.py`: reproducible module-specific NumPy streams
- `src/schemas.py`: contracts for the 16 required CSV tables and controlled vocabularies
- `src/markets.py`: markets and cities
- `src/entities.py`: users, addresses, restaurants, and delivery partners
- `src/behavior.py`: internal user behavior profiles
- `src/availability.py`: restaurant availability
- `src/orders.py`: chunked order generation
- `src/delivery.py`: delivery event state machine
- `src/experience.py`: ratings, issues, and refunds
- `src/promotions.py`: promotions and redemptions
- `src/finance.py`: order-level financials
- `src/optional_tables.py`: deferred optional tables
- `src/validation.py`: schema and integrity checks
- `src/export.py`: CSV output helpers
- `src/main.py`: planned orchestration order; no large-scale execution yet

Stage 2 also persists internal latent profiles, separate from raw table schemas:

- `data/processed/user_profiles.parquet`
- `data/processed/restaurant_profiles.parquet`
- `data/processed/partner_profiles.parquet`

These artifacts use `entity_id` plus latent behavioral, popularity, reliability, and operational variables. They are loaded by future stages through `load_user_profiles()` and `load_entity_profiles()` and are regenerated deterministically from the master seed.

## Required Tables

The schema registry defines these exact table names and the complete column-by-column contracts from the source specification:

`markets`, `cities`, `users`, `restaurants`, `delivery_partners`, `addresses`, `orders`, `order_items`, `delivery_events`, `restaurant_availability`, `ratings`, `order_issues`, `refunds`, `promotions`, `order_promotions`, and `order_financials`.

Delivery events use the required event types: `ORDER_PLACED`, `RESTAURANT_ACCEPTED`, `PREPARATION_STARTED`, `PARTNER_REQUESTED`, `PARTNER_ASSIGNED`, `PARTNER_ARRIVED`, `ORDER_PICKED_UP`, `ORDER_DELIVERED`, and `ORDER_CANCELLED`.

Latent behavioral values live in internal generator state and are not added to final CSV tables unless later approved as schema columns.

Nullable fields are represented with pandas nullable dtypes in the contract registry. The SQL type registry preserves the specified `INT`, `BIGINT`, `DECIMAL`, `VARCHAR`, `DATE`, `TIMESTAMP`, `BOOLEAN`, and `TEXT` declarations. `order_promotions` uses `(order_id, promotion_id)` as its composite key. No additional required tables or final-table columns are defined.

## Generation Order

1. Markets and cities
2. Users, addresses, restaurants, and delivery partners
3. Promotions and restaurant availability
4. Internal user behavior profiles
5. Chunked orders and order items
6. Delivery events
7. Ratings, issues, and refunds
8. Order promotions and order financials
9. Validation and CSV export

Foreign keys are selected from entity pools constrained by city, lifecycle dates, eligibility, and service area. Dependent tables are generated only after their parent tables exist.

Stage 2 partner allocation uses city demand weighted by `population * sqrt(population_density)`, then applies configured market partner density and a bounded restaurant-supply adjustment: `partner_weight = demand * partner_density * (0.75 + 0.25 * restaurant_density)`. This keeps partner supply related to population, density, expected demand, and restaurant supply without making any market outcome deterministic. The generated latent profiles are persisted separately in `data/processed/user_profiles.parquet`, `data/processed/restaurant_profiles.parquet`, and `data/processed/partner_profiles.parquet`; they are internal artifacts and are not raw CSV tables.

Stage 3 restaurant availability uses four snapshots per restaurant per week: Wednesday lunch, Wednesday dinner, Saturday lunch, and Saturday dinner. This produces about 5 million rows at the configured scale, captures weekday/weekend and lunch/dinner operational variation, and gives future orders a compact nearest-window mapping without generating hourly rows for every restaurant.

## Reproducibility and Scale

The initial configuration is:

- Master seed: `20260820`
- Users: `55,000`
- Restaurants: `12,000`
- Delivery partners: `12,000`
- Orders: `500,000`
- Date range: `2024-01-01` through `2025-12-31`
- Generation chunk size: `50,000` orders

Each module receives a deterministic NumPy random stream derived from the master seed. The eventual implementation will use vectorized NumPy/pandas operations and bounded chunks rather than creating all transactional data in one in-memory operation.

## Validation Approach

Before export, validation will check required columns, primary-key uniqueness, foreign-key membership, lifecycle and event timestamps, promotion eligibility, refund bounds, order-item ownership, financial reconciliation, controlled edge-case rates, and distribution summaries. The validation layer is designed to identify unrealistic output without assuming which market performs best.

## Assumptions

The original Uber Eats Dataset Generation Specification is the authoritative schema source. `src/schemas.py` mirrors its complete column lists, nullability, SQL types, composite key, and controlled vocabularies; latent behavioral variables remain internal to the generator.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m compileall -q src
python -m src.main
```

The final command only prints the planned pipeline at this stage; it does not generate data.

Partner supply is allocated from the same population and density demand base used for users, adjusted by configured partner density and restaurant-supply priors. This prevents lower-density markets from receiving disproportionate partner supply merely because partners used a weaker density exponent.
