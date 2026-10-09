-- Recurring daily windows from published schedules (NOT measured outages), in local Asia/Karachi
-- minutes of day. K-Electric: four daily cycles per feeder (a cycle may wrap midnight). IESCO:
-- scenario playbook slots per interruption level; the files never say which level is active.
with iesco as (
    select
        'iesco:' || s.circle || ':' || f.feeder_code as feeder_id,
        'iesco' as source,
        'scenario_level' as schedule_kind,
        s.level_hours as scenario_level_hours,
        row_number() over (
            partition by s.circle, s.sheet_row, s.level_hours order by s.slot_start_hour
        ) as window_no,
        s.slot_start_hour * 60 as start_minute_local,
        s.slot_end_hour * 60 as end_minute_local,
        false as wraps_midnight,
        60 as duration_minutes,
        f.source_sha256
    from {{ ref('stg_iesco_schedule_slot') }} as s
    inner join {{ ref('stg_iesco_feeder') }} as f
        on s.circle = f.circle and s.sheet_row = f.sheet_row
    left join {{ ref('quarantine_schedule_window') }} as q
        on q.circle = s.circle and q.sheet_row = s.sheet_row
        and q.level_hours = s.level_hours and q.slot_start_hour = s.slot_start_hour
    where q.sheet_row is null
),

ke as (
    select
        'ke:' || coalesce(j.list_name_norm, c.feeder_name_norm) as feeder_id,
        'kelectric' as source,
        'daily_cycle' as schedule_kind,
        cast(null as integer) as scenario_level_hours,
        c.cycle_no as window_no,
        c.start_minute_local,
        c.end_minute_local,
        c.wraps_midnight,
        c.minutes as duration_minutes,
        s.source_sha256
    from {{ ref('stg_ke_schedule_cycle') }} as c
    inner join {{ ref('stg_ke_schedule') }} as s on c.feeder_name_norm = s.feeder_name_norm
    left join {{ ref('int_ke_feeder_join') }} as j on c.feeder_name_norm = j.schedule_name_norm
),

unioned as (
    select * from iesco
    union all
    select * from ke
)

select
    u.feeder_id || ':' || coalesce(cast(u.scenario_level_hours as string), 'daily')
        || ':' || cast(u.window_no as string) as window_id,
    u.feeder_id,
    u.source,
    u.schedule_kind,
    u.scenario_level_hours,
    u.window_no,
    u.start_minute_local,
    u.end_minute_local,
    u.wraps_midnight,
    u.duration_minutes,
    d.effective_from,
    d.effective_basis,
    u.source_sha256
from unioned as u
left join {{ ref('source_documents') }} as d on u.source_sha256 = d.source_sha256
