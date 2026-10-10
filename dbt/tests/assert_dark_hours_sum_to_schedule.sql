-- Hourly dark minutes add back up to each feeder's scheduled daily minutes (per level for IESCO).
with by_hours as (
    select feeder_id, coalesce(scenario_level_hours, 0) as lvl, sum(dark_minutes) as minutes
    from {{ ref('mart_feeder_dark_hours') }}
    group by feeder_id, coalesce(scenario_level_hours, 0)
),

by_windows as (
    select feeder_id, coalesce(scenario_level_hours, 0) as lvl, sum(duration_minutes) as minutes
    from {{ ref('fct_schedule_window') }}
    group by feeder_id, coalesce(scenario_level_hours, 0)
)

select w.feeder_id, w.lvl, w.minutes as window_minutes, h.minutes as hour_minutes
from by_windows as w
left join by_hours as h on h.feeder_id = w.feeder_id and h.lvl = w.lvl
where h.minutes is null or h.minutes <> w.minutes
