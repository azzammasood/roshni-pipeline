-- At scenario level N every IESCO feeder has exactly N one-hour windows (after quarantine).
select feeder_id, scenario_level_hours, count(*) as windows
from {{ ref('fct_schedule_window') }}
where schedule_kind = 'scenario_level'
group by feeder_id, scenario_level_hours
having count(*) <> scenario_level_hours
