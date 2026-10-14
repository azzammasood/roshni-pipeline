-- NEPRA's order on K-Electric: outage bands per loss category as printed, with K-Electric's own
-- scheduled hours. NEPRA's analysis of data K-Electric supplied (the order states no period);
-- always attributed to NEPRA, never shown as Roshni's measurement. A band is above the schedule
-- when its lower bound is at or over the category's scheduled hours (as the order counts them).
select
    concat(b.category, ':', b.band) as band_id,
    c.order_date,
    b.category,
    c.feeders as category_feeders,
    c.consumers as category_consumers,
    c.avg_atc_loss_pct,
    c.scheduled_minutes_per_day,
    b.band,
    b.lower_minutes,
    b.upper_minutes,
    b.feeders,
    b.consumers,
    b.pct_feeders,
    b.pct_consumers,
    b.lower_minutes >= c.scheduled_minutes_per_day as above_schedule,
    c.source_file
from {{ source('parsed', 'nepra_ke_order_band') }} as b
inner join {{ source('parsed', 'nepra_ke_order_category') }} as c
    on b.category = c.category and b.source_sha256 = c.source_sha256
