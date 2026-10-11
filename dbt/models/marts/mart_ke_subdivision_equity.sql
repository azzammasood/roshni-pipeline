-- K-Electric scheduled hours aggregated to Karachi census sub-divisions (only IBCs with an
-- accepted same-name crosswalk), next to census indicators. Exploratory and descriptive:
-- listed feeders only, IBC and sub-division extents not verified, no causal reading.
with feeders as (
    select x.subdivision_area_id, x.subdivision_name, x.ibc, h.feeder_id,
           h.scheduled_hours_per_day, h.atc_loss_pct
    from {{ ref('ke_ibc_subdivision') }} as x
    inner join {{ ref('mart_ke_feeder_hours') }} as h on h.ibc = x.ibc
    where x.crosswalk_status = 'accepted'
),

agg as (
    select
        subdivision_area_id,
        subdivision_name,
        count(distinct ibc) as ibcs,
        count(*) as scheduled_feeders,
        round(100.0 * sum(case when scheduled_hours_per_day = 12 then 1 else 0 end) / count(*), 1)
            as share_12h_pct,
        round(avg(scheduled_hours_per_day), 2) as mean_scheduled_hours,
        round(avg(atc_loss_pct), 1) as mean_atc_loss_pct
    from feeders
    group by subdivision_area_id, subdivision_name
)

select
    a.*,
    round(c.literacy_pct, 1) as literacy_pct,
    round(c.degree_share_pct, 2) as degree_share_pct,
    round(c.pacca_share_pct, 1) as pacca_share_pct,
    c.avg_household_size,
    c.pop_total
from agg as a
left join {{ ref('dim_area_indicators') }} as c on c.area_id = a.subdivision_area_id
