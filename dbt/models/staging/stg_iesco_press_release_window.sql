select
    source_sha256,
    seq,
    release_no,
    release_period,
    outage_date,
    circle,
    feeder_name,
    start_local,
    end_local,
    start_utc,
    end_utc,
    flags,
    source_file,
    fetched_at
from {{ source('parsed', 'iesco_press_release_window') }}
