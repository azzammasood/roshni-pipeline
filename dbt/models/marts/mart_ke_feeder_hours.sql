-- K-Electric listed feeders with scheduled daily load-shed hours (schedule, not measured).
-- Shares computed from this mart are among LISTED feeders only: exempt feeders are not published.
select
    f.feeder_id,
    f.feeder_name,
    f.ibc,
    f.grid_name,
    f.category,
    f.atc_loss_pct,
    f.schedule_match_method,
    f.schedule_match_confidence,
    count(w.window_id) as cycles,
    sum(w.duration_minutes) / 60.0 as scheduled_hours_per_day,
    min(w.effective_from) as effective_from
from {{ ref('dim_feeder') }} as f
inner join {{ ref('fct_schedule_window') }} as w on f.feeder_id = w.feeder_id
where f.source = 'kelectric' and f.in_feeder_list
group by
    f.feeder_id,
    f.feeder_name,
    f.ibc,
    f.grid_name,
    f.category,
    f.atc_loss_pct,
    f.schedule_match_method,
    f.schedule_match_confidence
