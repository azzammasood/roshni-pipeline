-- Scheduled dark minutes per feeder and local hour of day (Asia/Karachi), from recurring
-- schedules: K-Electric daily cycles and IESCO scenario levels (one profile per level).
-- Schedule data, not measured outages. A window that wraps midnight is split into two parts.
with parts as (
    select
        feeder_id, source, schedule_kind, scenario_level_hours, effective_from,
        start_minute_local as part_start,
        case when wraps_midnight then 1440 else end_minute_local end as part_end
    from {{ ref('fct_schedule_window') }}

    union all

    select
        feeder_id, source, schedule_kind, scenario_level_hours, effective_from,
        0 as part_start,
        end_minute_local as part_end
    from {{ ref('fct_schedule_window') }}
    where wraps_midnight
),

overlap as (
    select
        p.feeder_id,
        p.source,
        p.schedule_kind,
        p.scenario_level_hours,
        p.effective_from,
        h.hour_of_day,
        greatest(
            0,
            least(p.part_end, (h.hour_of_day + 1) * 60) - greatest(p.part_start, h.hour_of_day * 60)
        ) as minutes
    from parts as p
    cross join {{ ref('hours_of_day') }} as h
)

select
    feeder_id,
    source,
    schedule_kind,
    scenario_level_hours,
    hour_of_day,
    sum(minutes) as dark_minutes,
    min(effective_from) as effective_from
from overlap
group by feeder_id, source, schedule_kind, scenario_level_hours, hour_of_day
having sum(minutes) > 0
