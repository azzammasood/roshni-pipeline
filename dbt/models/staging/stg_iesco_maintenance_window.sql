-- IESCO monthly maintenance schedules (owner approval 2026-10-18): one row per printed window,
-- every stored version of every circle's workbook. Announced maintenance, not load shedding and
-- not measurements. Later versions repeat earlier windows; fct_maintenance_window keeps one.
select
    item,
    sheet,
    sheet_row,
    serial,
    circle_as_printed,
    division,
    subdivision,
    grid,
    feeder_name,
    feeder_code_raw,
    feeder_code,
    outage_date,
    start_local,
    end_local,
    start_utc,
    end_utc,
    purpose,
    area_affected,
    flags,
    source_file,
    source_sha256,
    fetched_at
from {{ source('parsed', 'iesco_maintenance_window') }}
