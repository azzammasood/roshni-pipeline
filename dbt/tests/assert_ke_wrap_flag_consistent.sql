-- A K-Electric cycle wraps midnight exactly when its end is not after its start.
select window_id
from {{ ref('fct_schedule_window') }}
where schedule_kind = 'daily_cycle'
    and wraps_midnight <> (end_minute_local <= start_minute_local)
