"""Schema, referential-integrity, temporal, and business-rule validation."""

from collections.abc import Mapping

import pandas as pd

from .schemas import DELIVERY_EVENT_TYPES, ISSUE_TYPES, REFUND_TYPES, TABLE_SCHEMAS

ADDRESS_TYPES = {"HOME", "WORK", "OTHER"}
CAPACITY_STATUSES = {"NORMAL", "BUSY", "HIGH", "FULL"}
ORDER_STATUSES = {"DELIVERED", "CANCELLED"}
ITEM_STATUSES = {"FULFILLED", "MISSING", "SUBSTITUTED"}


def validate_schema(tables: Mapping[str, pd.DataFrame]) -> list[str]:
    """Return validation errors for missing tables, columns, or dtype contracts."""
    errors: list[str] = []
    for table_name, schema in TABLE_SCHEMAS.items():
        table = tables.get(table_name)
        if table is None:
            errors.append(f"Missing required table: {table_name}")
            continue
        missing = set(schema) - set(table.columns)
        errors.extend(f"{table_name}: missing column {column}" for column in sorted(missing))
    return errors


def validate_referential_integrity(tables: Mapping[str, pd.DataFrame]) -> list[str]:
    """Validate foreign keys once generated tables are supplied."""
    return []


def validate_markets_and_cities(markets: pd.DataFrame, cities: pd.DataFrame) -> list[str]:
    """Validate the generated market and city dimensions."""
    errors: list[str] = []
    required_market_count = 5
    if len(markets) != required_market_count:
        errors.append(f"markets: expected {required_market_count} rows, found {len(markets)}")
    if len(cities) < 2 * required_market_count:
        errors.append(f"cities: expected multiple cities per market, found {len(cities)}")

    for table_name, table in (("markets", markets), ("cities", cities)):
        missing_columns = set(TABLE_SCHEMAS[table_name]) - set(table.columns)
        errors.extend(
            f"{table_name}: missing column {column}"
            for column in sorted(missing_columns)
        )
        primary_key = "market_id" if table_name == "markets" else "city_id"
        if table[primary_key].duplicated().any():
            errors.append(f"{table_name}: duplicate {primary_key} values")
        required_columns = [column for column in TABLE_SCHEMAS[table_name] if column not in {"exit_date"}]
        null_columns = table[required_columns].isna().any()
        errors.extend(
            f"{table_name}: null values in required column {column}"
            for column in null_columns[null_columns].index
        )

    valid_market_ids = set(markets["market_id"].dropna().astype(int))
    invalid_market_ids = set(cities["market_id"].dropna().astype(int)) - valid_market_ids
    if invalid_market_ids:
        errors.append(f"cities: invalid market_id values {sorted(invalid_market_ids)}")

    market_launch_dates = markets.set_index("market_id")["launch_date"]
    if (cities["launch_date"] < cities["market_id"].map(market_launch_dates)).any():
        errors.append("cities: launch_date precedes corresponding market launch_date")

    if not cities["latitude"].between(-90, 90).all():
        errors.append("cities: latitude outside [-90, 90]")
    if not cities["longitude"].between(-180, 180).all():
        errors.append("cities: longitude outside [-180, 180]")
    if set(cities["market_id"]) != valid_market_ids:
        errors.append("cities: market/city relationship does not cover every market")
    return errors


def validate_entities(
    users: pd.DataFrame,
    restaurants: pd.DataFrame,
    partners: pd.DataFrame,
    markets: pd.DataFrame,
    cities: pd.DataFrame,
    config: object,
) -> list[str]:
    """Validate the users, restaurants, and delivery partners stage."""
    errors: list[str] = []
    tables = {
        "users": users,
        "restaurants": restaurants,
        "delivery_partners": partners,
    }
    primary_keys = {"users": "user_id", "restaurants": "restaurant_id", "delivery_partners": "partner_id"}
    nullable = {
        "users": {"acquisition_source", "mobility_signup_date", "membership_status", "membership_start_date"},
        "restaurants": {"offboard_date", "chain_flag", "restaurant_rating", "delivery_radius_km"},
        "delivery_partners": {"offboard_date", "vehicle_type", "partner_rating"},
    }
    for table_name, table in tables.items():
        schema = TABLE_SCHEMAS[table_name]
        missing = set(schema) - set(table.columns)
        errors.extend(f"{table_name}: missing column {column}" for column in sorted(missing))
        key = primary_keys[table_name]
        if key in table and table[key].duplicated().any():
            errors.append(f"{table_name}: duplicate {key} values")
        required = [column for column in schema if column not in nullable[table_name]]
        if set(required).issubset(table.columns):
            null_columns = table[required].isna().any()
            errors.extend(f"{table_name}: null values in required column {column}" for column in null_columns[null_columns].index)

    market_ids = set(markets["market_id"].astype(int))
    city_market = cities.set_index("city_id")["market_id"]
    market_launch = markets.set_index("market_id")["launch_date"]
    city_launch = cities.set_index("city_id")["launch_date"]
    for table_name, table in tables.items():
        city_column = "home_city_id" if table_name == "users" else "city_id"
        invalid_markets = set(table["market_id"].dropna().astype(int)) - market_ids
        if invalid_markets:
            errors.append(f"{table_name}: invalid market_id values {sorted(invalid_markets)}")
        invalid_cities = set(table[city_column].dropna().astype(int)) - set(city_market.index.astype(int))
        if invalid_cities:
            errors.append(f"{table_name}: invalid {city_column} values {sorted(invalid_cities)}")
        valid_rows = table[table[city_column].isin(city_market.index)]
        if not valid_rows.empty and (valid_rows["market_id"].to_numpy() != valid_rows[city_column].map(city_market).to_numpy()).any():
            errors.append(f"{table_name}: {city_column} and market_id relationship mismatch")
        if "onboard_date" in table and not valid_rows.empty and (valid_rows["onboard_date"] < valid_rows["city_id"].map(city_launch)).any():
            errors.append(f"{table_name}: onboard_date precedes city launch_date")
        if "onboard_date" in table and not valid_rows.empty and (valid_rows["onboard_date"] < valid_rows["market_id"].map(market_launch)).any():
            errors.append(f"{table_name}: onboard_date precedes market launch date")
        if "offboard_date" in table:
            offboarded = table[table["offboard_date"].notna()]
            if not offboarded.empty and (offboarded["offboard_date"] < offboarded["onboard_date"]).any():
                errors.append(f"{table_name}: offboard_date precedes onboard_date")

    user_signup = users["signup_timestamp"]
    if (user_signup < pd.Timestamp(config.start_date)).any() or (user_signup > pd.Timestamp(config.end_date) + pd.Timedelta(days=1)).any():
        errors.append("users: signup_timestamp outside configured generation period")
    user_city_launch = users["home_city_id"].map(city_launch)
    if (user_signup.dt.normalize() < user_city_launch).any():
        errors.append("users: signup_timestamp precedes home city launch")
    mobility_rows = users[users["is_uber_mobility_user"]]
    if not mobility_rows.empty:
        if mobility_rows["mobility_signup_date"].isna().any():
            errors.append("users: mobility users missing mobility_signup_date")
        if (mobility_rows["mobility_signup_date"] > mobility_rows["signup_timestamp"].dt.date).any():
            errors.append("users: mobility_signup_date after signup_timestamp")
    members = users[users["membership_status"].notna()]
    if not members.empty:
        if members["membership_start_date"].isna().any():
            errors.append("users: members missing membership_start_date")
        if (members["membership_start_date"] < members["signup_timestamp"].dt.date).any():
            errors.append("users: membership_start_date before signup date")
    if not restaurants.empty and not restaurants["restaurant_rating"].dropna().between(1, 5).all():
        errors.append("restaurants: rating outside [1, 5]")
    if not restaurants.empty and not restaurants["delivery_radius_km"].dropna().gt(0).all():
        errors.append("restaurants: delivery radius is not positive")
    if not partners.empty and not partners["partner_rating"].dropna().between(1, 5).all():
        errors.append("delivery_partners: rating outside [1, 5]")
    if len(users) != config.target_users:
        errors.append(f"users: expected {config.target_users} rows, found {len(users)}")
    if len(restaurants) != config.target_restaurants:
        errors.append(f"restaurants: expected {config.target_restaurants} rows, found {len(restaurants)}")
    if len(partners) != config.target_delivery_partners:
        errors.append(f"delivery_partners: expected {config.target_delivery_partners} rows, found {len(partners)}")
    return errors


def validate_entity_distributions(
    users: pd.DataFrame,
    restaurants: pd.DataFrame,
    partners: pd.DataFrame,
    user_profiles: pd.DataFrame,
    restaurant_profiles: pd.DataFrame,
) -> list[str]:
    """Check basic non-uniformity and latent-profile sanity for this stage."""
    errors: list[str] = []
    for table_name, table in (("users", users), ("restaurants", restaurants), ("delivery_partners", partners)):
        city_column = "home_city_id" if table_name == "users" else "city_id"
        if table[city_column].nunique() < 2:
            errors.append(f"{table_name}: entities are concentrated in fewer than two cities")
    if restaurant_profiles["popularity_score"].quantile(0.95) <= restaurant_profiles["popularity_score"].median() * 1.5:
        errors.append("restaurants: popularity profile is not sufficiently heavy-tailed")
    if user_profiles["segment"].nunique() < 3:
        errors.append("users: behavioral profiles lack segment variation")
    return errors


def validate_stage3(
    addresses: pd.DataFrame,
    availability: pd.DataFrame,
    users: pd.DataFrame,
    restaurants: pd.DataFrame,
    cities: pd.DataFrame,
    config: object,
) -> list[str]:
    """Validate addresses and restaurant availability for the third stage."""
    errors: list[str] = []
    for table_name, table, primary_key in (
        ("addresses", addresses, "address_id"),
        ("restaurant_availability", availability, "availability_id"),
    ):
        missing = set(TABLE_SCHEMAS[table_name]) - set(table.columns)
        errors.extend(f"{table_name}: missing column {column}" for column in sorted(missing))
        if primary_key in table and table[primary_key].duplicated().any():
            errors.append(f"{table_name}: duplicate {primary_key} values")

    user_ids = set(users["user_id"])
    city_ids = set(cities["city_id"])
    restaurant_ids = set(restaurants["restaurant_id"])
    if not set(addresses["user_id"]).issubset(user_ids):
        errors.append("addresses: invalid user_id foreign key")
    if not set(addresses["city_id"]).issubset(city_ids):
        errors.append("addresses: invalid city_id foreign key")
    user_city = users.set_index("user_id")["home_city_id"]
    if not addresses.empty and (addresses["city_id"].to_numpy() != addresses["user_id"].map(user_city).to_numpy()).any():
        errors.append("addresses: city_id does not match user's home_city_id")
    if not addresses.empty and (addresses["created_at"] < addresses["user_id"].map(users.set_index("user_id")["signup_timestamp"])).any():
        errors.append("addresses: created_at precedes user signup_timestamp")
    if not addresses["address_type"].isin(ADDRESS_TYPES).all():
        errors.append("addresses: invalid address_type vocabulary")
    city_lookup = cities.set_index("city_id")
    if not addresses.empty:
        city_lat = addresses["city_id"].map(city_lookup["latitude"])
        city_lon = addresses["city_id"].map(city_lookup["longitude"])
        lat_distance = (addresses["latitude"] - city_lat).abs()
        lon_distance = (addresses["longitude"] - city_lon).abs()
        if (lat_distance > 0.5).any() or (lon_distance > 0.5).any():
            errors.append("addresses: coordinates are implausibly far from city centers")
        if not addresses[["latitude", "longitude"]].notna().all().all():
            errors.append("addresses: null coordinates")

    if not set(availability["restaurant_id"]).issubset(restaurant_ids):
        errors.append("restaurant_availability: invalid restaurant_id foreign key")
    start = pd.Timestamp(config.start_date)
    end = pd.Timestamp(config.end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    if not availability["timestamp"].between(start, end).all():
        errors.append("restaurant_availability: timestamp outside configured date range")
    if not availability["capacity_status"].isin(CAPACITY_STATUSES).all():
        errors.append("restaurant_availability: invalid capacity_status vocabulary")
    accepting = availability["is_accepting_orders"]
    prep = availability["estimated_prep_time_min"]
    if prep[accepting].isna().any() or not prep[accepting].dropna().gt(0).all():
        errors.append("restaurant_availability: accepting rows require positive prep time")
    if prep[~accepting].notna().any():
        errors.append("restaurant_availability: non-accepting rows must have null prep time")
    if (availability.loc[availability["capacity_status"] == "FULL", "is_accepting_orders"] == False).mean() < 0.5:
        errors.append("restaurant_availability: FULL status is not associated with non-acceptance")
    if availability["timestamp"].dt.hour.nunique() < 2:
        errors.append("restaurant_availability: insufficient time-window variation")
    if availability["restaurant_id"].nunique() < 2:
        errors.append("restaurant_availability: insufficient restaurant variation")
    if availability["capacity_status"].nunique() < 3:
        errors.append("restaurant_availability: insufficient capacity-status variation")
    if len(addresses) < len(users):
        errors.append("addresses: fewer than one address per user")
    return errors


def validate_stage4(
    orders: pd.DataFrame,
    order_items: pd.DataFrame,
    users: pd.DataFrame,
    restaurants: pd.DataFrame,
    partners: pd.DataFrame,
    addresses: pd.DataFrame,
    cities: pd.DataFrame,
    config: object,
) -> list[str]:
    """Validate orders and order items without requiring downstream tables."""
    errors: list[str] = []
    for table_name, table, key in (
        ("orders", orders, "order_id"),
        ("order_items", order_items, "order_item_id"),
    ):
        missing = set(TABLE_SCHEMAS[table_name]) - set(table.columns)
        errors.extend(f"{table_name}: missing column {column}" for column in sorted(missing))
        if key in table and table[key].duplicated().any():
            errors.append(f"{table_name}: duplicate {key} values")
        if set(TABLE_SCHEMAS[table_name]).issubset(table.columns):
            required = {"delivery_partner_id", "actual_delivery_timestamp", "cancelled_at", "cancellation_reason"} if table_name == "orders" else set()
            null_columns = table[[column for column in TABLE_SCHEMAS[table_name] if column not in required]].isna().any()
            errors.extend(f"{table_name}: null values in required column {column}" for column in null_columns[null_columns].index)

    user_lookup = users.set_index("user_id")
    restaurant_lookup = restaurants.set_index("restaurant_id")
    partner_lookup = partners.set_index("partner_id")
    address_lookup = addresses.set_index("address_id")
    city_lookup = cities.set_index("city_id")
    if not set(orders["user_id"]).issubset(user_lookup.index):
        errors.append("orders: invalid user_id foreign key")
    if not set(orders["restaurant_id"]).issubset(restaurant_lookup.index):
        errors.append("orders: invalid restaurant_id foreign key")
    if not set(orders["address_id"]).issubset(address_lookup.index):
        errors.append("orders: invalid address_id foreign key")
    if not set(order_items["order_id"]).issubset(set(orders["order_id"])):
        errors.append("order_items: invalid order_id foreign key")
    partner_ids = set(orders["delivery_partner_id"].dropna())
    if not partner_ids.issubset(partner_lookup.index):
        errors.append("orders: invalid delivery_partner_id foreign key")
    if not orders.empty:
        user_market = orders["user_id"].map(user_lookup["market_id"])
        user_city = orders["user_id"].map(user_lookup["home_city_id"])
        restaurant_market = orders["restaurant_id"].map(restaurant_lookup["market_id"])
        restaurant_city = orders["restaurant_id"].map(restaurant_lookup["city_id"])
        if (orders["market_id"] != user_market).any() or (orders["market_id"] != restaurant_market).any():
            errors.append("orders: market_id inconsistent with user or restaurant")
        if (orders["city_id"] != user_city).any() or (orders["city_id"] != restaurant_city).any():
            errors.append("orders: city_id inconsistent with user or restaurant")
        if (orders["address_id"].map(address_lookup["user_id"]) != orders["user_id"]).any():
            errors.append("orders: address_id does not belong to user")
        partner_city = orders["delivery_partner_id"].map(partner_lookup["city_id"])
        partner_market = orders["delivery_partner_id"].map(partner_lookup["market_id"])
        assigned = orders["delivery_partner_id"].notna()
        if (partner_city[assigned] != orders.loc[assigned, "city_id"]).any() or (partner_market[assigned] != orders.loc[assigned, "market_id"]).any():
            errors.append("orders: delivery partner is not in order city/market")

    if not orders["order_status"].isin(ORDER_STATUSES).all():
        errors.append("orders: invalid order_status vocabulary")
    start = pd.Timestamp(config.start_date)
    end = pd.Timestamp(config.end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    if not orders["order_timestamp"].between(start, end).all():
        errors.append("orders: order_timestamp outside configured range")
    delivered = orders["order_status"] == "DELIVERED"
    cancelled = orders["order_status"] == "CANCELLED"
    if orders.loc[delivered, "actual_delivery_timestamp"].isna().any() or orders.loc[delivered, "cancelled_at"].notna().any() or orders.loc[delivered, "cancellation_reason"].notna().any():
        errors.append("orders: delivered lifecycle fields are inconsistent")
    if orders.loc[cancelled, "actual_delivery_timestamp"].notna().any() or orders.loc[cancelled, "cancelled_at"].isna().any() or orders.loc[cancelled, "cancellation_reason"].isna().any():
        errors.append("orders: cancelled lifecycle fields are inconsistent")
    if (orders.loc[delivered, "promised_delivery_timestamp"] <= orders.loc[delivered, "order_timestamp"]).any() or (orders.loc[delivered, "actual_delivery_timestamp"] <= orders.loc[delivered, "order_timestamp"]).any():
        errors.append("orders: delivered timestamps are not after order_timestamp")
    if (orders.loc[cancelled, "cancelled_at"] <= orders.loc[cancelled, "order_timestamp"]).any():
        errors.append("orders: cancelled_at is not after order_timestamp")
    if not orders["order_status"].isin(ORDER_STATUSES).all():
        errors.append("orders: unsupported order status")
    money_columns = ["subtotal", "delivery_fee", "tax", "discount_amount", "total_paid"]
    if (orders[money_columns] < 0).any().any():
        errors.append("orders: negative monetary value")
    expected_total = (orders["subtotal"] + orders["delivery_fee"] + orders["tax"] - orders["discount_amount"]).round(2)
    if not (orders["total_paid"].round(2).sub(expected_total).abs() <= 0.011).all():
        errors.append("orders: total_paid arithmetic mismatch")
    if not order_items["item_status"].isin(ITEM_STATUSES).all():
        errors.append("order_items: invalid item_status vocabulary")
    if order_items["quantity"].le(0).any() or order_items["unit_price"].le(0).any():
        errors.append("order_items: non-positive quantity or unit_price")
    if (order_items["missing_item_flag"] & (order_items["item_status"] != "MISSING")).any() or (order_items["substitution_flag"] & (order_items["item_status"] != "SUBSTITUTED")).any():
        errors.append("order_items: item flags inconsistent with status")
    if ((order_items["item_status"] == "MISSING") & order_items["substitution_flag"]).any() or ((order_items["item_status"] == "MISSING") & order_items["missing_item_flag"].eq(False)).any():
        errors.append("order_items: impossible missing/substitution combination")
    item_counts = order_items.groupby("order_id").size()
    if not orders["order_id"].isin(item_counts.index).all():
        errors.append("order_items: at least one item required for every order")
    if len(orders) != config.target_orders:
        errors.append(f"orders: expected {config.target_orders} rows, found {len(orders)}")
    return errors


def validate_stage5(
    events: pd.DataFrame,
    orders: pd.DataFrame,
    partners: pd.DataFrame,
    config: object,
) -> list[str]:
    """Validate delivery events without requiring downstream experience tables."""
    errors: list[str] = []
    schema = TABLE_SCHEMAS["delivery_events"]
    missing = set(schema) - set(events.columns)
    errors.extend(f"delivery_events: missing column {column}" for column in sorted(missing))
    if not events.empty and events["event_id"].duplicated().any():
        errors.append("delivery_events: duplicate event_id values")
    required = ["event_id", "order_id", "event_type", "event_timestamp"]
    if not events.empty and events[required].isna().any().any():
        errors.append("delivery_events: null required values")
    order_lookup = orders.set_index("order_id")
    partner_lookup = partners.set_index("partner_id")
    if not set(events["order_id"]).issubset(order_lookup.index):
        errors.append("delivery_events: invalid order_id foreign key")
    event_partner_ids = set(events["partner_id"].dropna())
    if not event_partner_ids.issubset(partner_lookup.index):
        errors.append("delivery_events: invalid partner_id foreign key")
    if not events["event_type"].isin(DELIVERY_EVENT_TYPES).all():
        errors.append("delivery_events: invalid event_type vocabulary")

    for order_id, order_events in events.groupby("order_id", sort=False):
        order = order_lookup.loc[order_id]
        order_events = order_events.sort_values(["event_timestamp", "event_id"])
        event_types = order_events["event_type"].tolist()
        if event_types[0] != "ORDER_PLACED":
            errors.append(f"delivery_events: order {order_id} does not start with ORDER_PLACED")
        terminal = "ORDER_DELIVERED" if order["order_status"] == "DELIVERED" else "ORDER_CANCELLED"
        if event_types[-1] != terminal:
            errors.append(f"delivery_events: order {order_id} has invalid terminal event")
        if order["order_status"] == "DELIVERED" and event_types != list(DELIVERY_EVENT_TYPES[:8]):
            errors.append(f"delivery_events: delivered order {order_id} has incomplete lifecycle")
        if order["order_status"] == "CANCELLED" and "ORDER_DELIVERED" in event_types:
            errors.append(f"delivery_events: cancelled order {order_id} has ORDER_DELIVERED")
        if any(left > right for left, right in zip(order_events["event_timestamp"], order_events["event_timestamp"][1:])):
            errors.append(f"delivery_events: order {order_id} event timestamps are out of order")
        if (order_events["event_timestamp"] < order["order_timestamp"]).any():
            errors.append(f"delivery_events: order {order_id} event precedes order timestamp")
        terminal_timestamp = order_events.iloc[-1]["event_timestamp"]
        expected_terminal = order["actual_delivery_timestamp"] if terminal == "ORDER_DELIVERED" else order["cancelled_at"]
        if terminal_timestamp != expected_terminal:
            errors.append(f"delivery_events: order {order_id} terminal timestamp mismatch")
        assigned_events = order_events[order_events["event_type"].isin(["PARTNER_ASSIGNED", "PARTNER_ARRIVED", "ORDER_PICKED_UP", "ORDER_DELIVERED"])]
        if order["order_status"] == "DELIVERED":
            if assigned_events["partner_id"].isna().any() or (assigned_events["partner_id"] != order["delivery_partner_id"]).any():
                errors.append(f"delivery_events: delivered order {order_id} partner mismatch")
    if len(events) == 0 and len(orders) > 0:
        errors.append("delivery_events: no events generated")
    if not events.empty:
        covered = set(events["order_id"])
        if not set(orders["order_id"]).issubset(covered):
            errors.append("delivery_events: not every order is covered")
    return errors


def validate_stage6(
    ratings: pd.DataFrame,
    issues: pd.DataFrame,
    refunds: pd.DataFrame,
    orders: pd.DataFrame,
    users: pd.DataFrame,
    restaurants: pd.DataFrame,
    config: object,
) -> list[str]:
    """Validate ratings, issues, and refunds without requiring later stages."""
    errors: list[str] = []
    table_specs = (
        ("ratings", ratings, "rating_id"),
        ("order_issues", issues, "issue_id"),
        ("refunds", refunds, "refund_id"),
    )
    for table_name, table, primary_key in table_specs:
        missing = set(TABLE_SCHEMAS[table_name]) - set(table.columns)
        errors.extend(f"{table_name}: missing column {column}" for column in sorted(missing))
        if primary_key in table and table[primary_key].duplicated().any():
            errors.append(f"{table_name}: duplicate {primary_key} values")
        if not table.empty:
            nullable = {"resolved_at"} if table_name == "order_issues" else set()
            required_columns = [column for column in TABLE_SCHEMAS[table_name] if column not in nullable]
            null_columns = table[required_columns].isna().any()
            errors.extend(f"{table_name}: null required value in {column}" for column in null_columns[null_columns].index)

    order_lookup = orders.set_index("order_id")
    user_lookup = users.set_index("user_id")
    restaurant_lookup = restaurants.set_index("restaurant_id")
    for table_name, table in (("ratings", ratings), ("order_issues", issues), ("refunds", refunds)):
        if not set(table["order_id"]).issubset(order_lookup.index):
            errors.append(f"{table_name}: invalid order_id foreign key")
    if not ratings.empty:
        if not set(ratings["user_id"]).issubset(user_lookup.index):
            errors.append("ratings: invalid user_id foreign key")
        if not set(ratings["restaurant_id"]).issubset(restaurant_lookup.index):
            errors.append("ratings: invalid restaurant_id foreign key")
        if (ratings["user_id"].map(user_lookup["market_id"]) != ratings["order_id"].map(order_lookup["market_id"])).any():
            errors.append("ratings: user/order relationship mismatch")
        if not ratings["rating"].between(1, 5).all():
            errors.append("ratings: rating outside [1, 5]")
        if (~ratings["order_id"].map(order_lookup["order_status"]).eq("DELIVERED")).any():
            errors.append("ratings: rating attached to non-delivered order")
    if not issues.empty:
        if not issues["issue_type"].isin(ISSUE_TYPES).all():
            errors.append("order_issues: invalid issue_type vocabulary")
        if not issues["severity"].isin({"LOW", "MEDIUM", "HIGH"}).all():
            errors.append("order_issues: invalid severity vocabulary")
        issue_order_timestamps = issues["order_id"].map(order_lookup["order_timestamp"])
        issue_terminal = issues["order_id"].map(order_lookup["actual_delivery_timestamp"]).fillna(issues["order_id"].map(order_lookup["cancelled_at"]))
        if (issues["reported_at"] < issue_order_timestamps).any() or (issues["reported_at"] > issue_terminal).any():
            errors.append("order_issues: reported_at outside order lifecycle")
        resolved = issues["resolved_at"].notna()
        if (issues.loc[resolved, "resolved_at"] < issues.loc[resolved, "reported_at"]).any():
            errors.append("order_issues: resolved_at precedes reported_at")
    if not refunds.empty:
        if not refunds["refund_type"].isin(REFUND_TYPES).all():
            errors.append("refunds: invalid refund_type vocabulary")
        if not set(refunds["user_id"]).issubset(user_lookup.index):
            errors.append("refunds: invalid user_id foreign key")
        if (refunds["user_id"] != refunds["order_id"].map(order_lookup["user_id"])).any():
            errors.append("refunds: user/order relationship mismatch")
        if refunds["refund_amount"].le(0).any():
            errors.append("refunds: non-positive refund amount")
        order_paid = refunds["order_id"].map(order_lookup["total_paid"])
        if (refunds["refund_amount"] > order_paid).any():
            errors.append("refunds: amount exceeds order total")
        refund_order_timestamps = refunds["order_id"].map(order_lookup["order_timestamp"])
        if (refunds["refund_timestamp"] < refund_order_timestamps).any():
            errors.append("refunds: refund_timestamp precedes order")
    return errors


def validate_stage7(
    promotions: pd.DataFrame,
    order_promotions: pd.DataFrame,
    orders: pd.DataFrame,
    config: object,
) -> list[str]:
    """Validate promotions and their order redemptions without financials."""
    errors: list[str] = []
    for table_name, table, key in (("promotions", promotions, "promotion_id"), ("order_promotions", order_promotions, None)):
        missing = set(TABLE_SCHEMAS[table_name]) - set(table.columns)
        errors.extend(f"{table_name}: missing column {column}" for column in sorted(missing))
        if key and table[key].duplicated().any():
            errors.append(f"{table_name}: duplicate {key} values")
    if not order_promotions.empty and order_promotions.duplicated(["order_id", "promotion_id"]).any():
        errors.append("order_promotions: duplicate composite key")
    required_promotions = [column for column in TABLE_SCHEMAS["promotions"] if column not in {"minimum_order_value", "maximum_discount"}]
    if not promotions.empty:
        errors.extend(f"promotions: null required value in {column}" for column in promotions[required_promotions].isna().any()[lambda series: series].index)
        if (promotions["start_date"] > promotions["end_date"]).any():
            errors.append("promotions: start_date after end_date")
        if not promotions["discount_type"].isin({"PERCENTAGE", "FIXED_AMOUNT"}).all():
            errors.append("promotions: invalid discount_type")
        if promotions["discount_value"].le(0).any() or promotions["minimum_order_value"].dropna().lt(0).any() or promotions["maximum_discount"].dropna().le(0).any():
            errors.append("promotions: invalid discount bounds")
        if not promotions["promotion_type"].isin({"FIRST_ORDER", "WEEKDAY", "WEEKEND", "MEMBERSHIP", "REACTIVATION"}).all():
            errors.append("promotions: invalid promotion_type")
        if (promotions["start_date"] < pd.Timestamp(config.start_date)).any() or (promotions["end_date"] > pd.Timestamp(config.end_date)).any():
            errors.append("promotions: date outside configured range")
    if not order_promotions.empty:
        if not set(order_promotions["order_id"]).issubset(set(orders["order_id"])):
            errors.append("order_promotions: invalid order_id foreign key")
        if not set(order_promotions["promotion_id"]).issubset(set(promotions["promotion_id"])):
            errors.append("order_promotions: invalid promotion_id foreign key")
        order_lookup = orders.set_index("order_id")
        promotion_lookup = promotions.set_index("promotion_id")
        order_dates = order_promotions["order_id"].map(order_lookup["order_timestamp"])
        selected_promotions = order_promotions["promotion_id"].map(promotion_lookup["start_date"])
        selected_end = order_promotions["promotion_id"].map(promotion_lookup["end_date"])
        if (order_dates < pd.to_datetime(selected_promotions)).any() or (order_dates > pd.to_datetime(selected_end)).any():
            errors.append("order_promotions: redemption outside promotion dates")
        order_subtotals = order_promotions["order_id"].map(order_lookup["subtotal"])
        minimums = order_promotions["promotion_id"].map(promotion_lookup["minimum_order_value"])
        if (order_subtotals < minimums).any():
            errors.append("order_promotions: order below promotion minimum")
        order_discounts = order_promotions["order_id"].map(order_lookup["discount_amount"])
        if (order_promotions["discount_amount"] <= 0).any() or (order_promotions["discount_amount"] > order_discounts + 0.011).any():
            errors.append("order_promotions: discount exceeds order discount")
    return errors


def validate_stage8(financials: pd.DataFrame, orders: pd.DataFrame, config: object) -> list[str]:
    """Validate order financials without requiring any later stage."""
    errors: list[str] = []
    schema = TABLE_SCHEMAS["order_financials"]
    missing = set(schema) - set(financials.columns)
    errors.extend(f"order_financials: missing column {column}" for column in sorted(missing))
    if list(financials.columns) != list(schema):
        errors.append("order_financials: column order mismatch")
    if financials["order_id"].duplicated().any():
        errors.append("order_financials: duplicate order_id values")
    if not set(financials["order_id"]).issubset(set(orders["order_id"])):
        errors.append("order_financials: invalid order_id foreign key")
    if set(financials["order_id"]) != set(orders["order_id"]):
        errors.append("order_financials: not exactly one row per order")
    monetary = [column for column in schema if column != "order_id"]
    if financials[monetary].isna().any().any():
        errors.append("order_financials: null monetary value")
    if (financials[monetary].drop(columns=["contribution_margin"], errors="ignore") < 0).any().any():
        errors.append("order_financials: negative revenue or cost value")
    revenue = financials["restaurant_commission"] + financials["delivery_revenue"] + financials["service_fee"] + financials["advertising_revenue"]
    costs = financials["promotion_cost"] + financials["delivery_partner_cost"] + financials["payment_processing_cost"] + financials["support_cost"]
    expected_margin = (revenue - costs).round(2)
    if (financials["contribution_margin"] - expected_margin).abs().gt(0.011).any():
        errors.append("order_financials: contribution_margin arithmetic mismatch")
    if len(financials) != config.target_orders:
        errors.append(f"order_financials: expected {config.target_orders} rows, found {len(financials)}")
    if not financials["contribution_margin"].lt(0).any():
        errors.append("order_financials: no negative contribution margins")
    if not financials["contribution_margin"].gt(0).any():
        errors.append("order_financials: no positive contribution margins")
    return errors
