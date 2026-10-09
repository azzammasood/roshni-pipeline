select
    circle,
    sheet_row,
    feeder_code,
    level_hours,
    slot_start_hour,
    slot_end_hour
from {{ source('parsed', 'iesco_schedule_slot') }}
