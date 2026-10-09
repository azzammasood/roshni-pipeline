select
    feeder_name,
    feeder_name_norm,
    grid,
    total_minutes,
    flags,
    page,
    source_file,
    source_sha256,
    fetched_at
from {{ source('parsed', 'kelectric_schedule') }}
