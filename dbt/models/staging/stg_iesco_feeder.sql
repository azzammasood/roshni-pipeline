select
    circle,
    sheet_row,
    serial,
    grid_name,
    feeder_name,
    feeder_code_raw,
    feeder_code,
    flags,
    source_file,
    source_sha256,
    fetched_at
from {{ source('parsed', 'iesco_feeder') }}
