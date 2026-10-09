-- Every K-Electric feeder with a schedule has exactly 4 cycles totalling 6 h or 12 h.
select feeder_id, count(*) as cycles, sum(duration_minutes) as minutes
from {{ ref('fct_schedule_window') }}
where schedule_kind = 'daily_cycle'
group by feeder_id
having count(*) <> 4 or sum(duration_minutes) not in (360, 720)
