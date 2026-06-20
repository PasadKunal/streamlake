"""PyArrow schemas for all Gold Delta tables."""
import pyarrow as pa

GOLD_DAU_SCHEMA = pa.schema([
    pa.field("event_date",       pa.string(),  nullable=False),
    pa.field("country_code",     pa.string(),  nullable=False),
    pa.field("device_type",      pa.string(),  nullable=False),
    pa.field("unique_users",     pa.int64(),   nullable=False),
    pa.field("total_sessions",   pa.int64(),   nullable=False),
    pa.field("total_events",     pa.int64(),   nullable=False),
    pa.field("gold_computed_ms", pa.int64(),   nullable=False),
])

GOLD_REVENUE_SCHEMA = pa.schema([
    pa.field("event_date",            pa.string(),  nullable=False),
    pa.field("country_code",          pa.string(),  nullable=False),
    pa.field("product_id",            pa.string(),  nullable=False),
    pa.field("total_purchases",       pa.int64(),   nullable=False),
    pa.field("total_revenue_cents",   pa.int64(),   nullable=False),
    pa.field("avg_order_value_cents", pa.float64(), nullable=False),
    pa.field("gold_computed_ms",      pa.int64(),   nullable=False),
])

GOLD_FUNNEL_SCHEMA = pa.schema([
    pa.field("event_date",          pa.string(),  nullable=False),
    pa.field("country_code",        pa.string(),  nullable=False),
    pa.field("total_page_views",    pa.int64(),   nullable=False),
    pa.field("total_add_to_carts",  pa.int64(),   nullable=False),
    pa.field("total_purchases",     pa.int64(),   nullable=False),
    pa.field("view_to_cart_pct",    pa.float64(), nullable=False),
    pa.field("cart_to_purchase_pct",pa.float64(), nullable=False),
    pa.field("gold_computed_ms",    pa.int64(),   nullable=False),
])

GOLD_USER_SIGNALS_SCHEMA = pa.schema([
    pa.field("user_id",                pa.string(),  nullable=False),
    pa.field("last_seen_date",         pa.string(),  nullable=False),
    pa.field("days_since_last_session",pa.int64(),   nullable=False),
    pa.field("total_sessions_7d",      pa.int64(),   nullable=False),
    pa.field("total_events_7d",        pa.int64(),   nullable=False),
    pa.field("total_purchases_7d",     pa.int64(),   nullable=False),
    pa.field("total_revenue_7d_cents", pa.int64(),   nullable=False),
    pa.field("is_churned",             pa.bool_(),   nullable=False),
    pa.field("churn_risk_score",       pa.float64(), nullable=False),
    pa.field("signal_date",            pa.string(),  nullable=False),
    pa.field("gold_computed_ms",       pa.int64(),   nullable=False),
])
