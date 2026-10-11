-- Descriptive equity figures per K-Electric IBC area. Counts and shares are AMONG LISTED FEEDERS
-- ONLY (feeders exempt from load shedding are not published). Schedule data, not measurements.
with listed as (
    select feeder_id, ibc, category, atc_loss_pct, has_schedule
    from {{ ref('dim_feeder') }}
    where source = 'kelectric' and in_feeder_list
),

hours as (
    select feeder_id, scheduled_hours_per_day from {{ ref('mart_ke_feeder_hours') }}
)

select
    l.ibc,
    count(*) as listed_feeders,
    sum(case when l.has_schedule then 1 else 0 end) as scheduled_feeders,
    sum(case when h.scheduled_hours_per_day = 12 then 1 else 0 end) as feeders_12h,
    sum(case when h.scheduled_hours_per_day = 6 then 1 else 0 end) as feeders_6h,
    round(
        100.0 * sum(case when h.scheduled_hours_per_day = 12 then 1 else 0 end)
        / nullif(count(h.feeder_id), 0), 1
    ) as share_12h_pct,
    round(avg(h.scheduled_hours_per_day), 2) as mean_scheduled_hours,
    count(l.atc_loss_pct) as feeders_with_loss,
    round(avg(l.atc_loss_pct), 1) as mean_atc_loss_pct,
    sum(case when l.category = 'Medium' then 1 else 0 end) as medium_feeders,
    sum(case when l.category = 'High' then 1 else 0 end) as high_feeders,
    sum(case when l.category = 'Very High' then 1 else 0 end) as very_high_feeders,
    min(x.subdivision_name) as census_subdivision,
    min(x.crosswalk_status) as crosswalk_status
from listed as l
left join hours as h on h.feeder_id = l.feeder_id
left join {{ ref('ke_ibc_subdivision') }} as x on x.ibc = l.ibc
group by l.ibc
