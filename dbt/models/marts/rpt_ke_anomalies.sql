-- Rule-based observations on the K-Electric list and schedule. Observations, not findings of
-- unfairness: the published category drives hours, and category is not a pure function of loss.
with f as (
    select d.*, h.scheduled_hours_per_day
    from {{ ref('dim_feeder') }} as d
    left join {{ ref('mart_ke_feeder_hours') }} as h on h.feeder_id = d.feeder_id
    where d.source = 'kelectric'
),

band as (
    -- Loss range where Medium and High overlap: from the lowest High loss to the highest Medium.
    select
        min(case when category = 'High' then atc_loss_pct end) as band_low,
        max(case when category = 'Medium' then atc_loss_pct end) as band_high
    from f
    where in_feeder_list
)

select 'medium_category_at_12h' as rule,
       'Medium-loss feeders scheduled 12 h (Medium is otherwise 6 h)' as description,
       count(*) as feeders
from f where category = 'Medium' and scheduled_hours_per_day = 12

union all
select 'listed_without_schedule', 'Listed feeders with no schedule row', count(*)
from f where in_feeder_list and not has_schedule

union all
select 'schedule_without_listing', 'Schedule rows whose feeder is not in the list', count(*)
from f where not in_feeder_list

union all
select 'listed_without_loss', 'Listed feeders with no published ATC loss', count(*)
from f where in_feeder_list and atc_loss_pct is null

union all
select 'medium_in_overlap_band',
       'Scheduled Medium feeders whose loss lies in the Medium/High overlap band', count(*)
from f cross join band
where in_feeder_list and has_schedule and category = 'Medium'
    and atc_loss_pct between band_low and band_high

union all
select 'high_in_overlap_band',
       'Scheduled High feeders whose loss lies in the Medium/High overlap band', count(*)
from f cross join band
where in_feeder_list and has_schedule and category = 'High'
    and atc_loss_pct between band_low and band_high
