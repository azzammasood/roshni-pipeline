select
    feeder_name_norm,
    grid,
    cycle_no,
    start_hhmm,
    end_hhmm,
    wraps_midnight,
    minutes,
    cast(substr(start_hhmm, 1, 2) as integer) * 60
        + cast(substr(start_hhmm, 3, 2) as integer) as start_minute_local,
    cast(substr(end_hhmm, 1, 2) as integer) * 60
        + cast(substr(end_hhmm, 3, 2) as integer) as end_minute_local
from {{ source('parsed', 'kelectric_schedule_cycle') }}
