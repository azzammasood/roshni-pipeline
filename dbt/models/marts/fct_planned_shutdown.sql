-- Dated planned-shutdown windows announced in IESCO press releases (announcements, not
-- measurements). Feeder and circle names are as printed; matching to dim_feeder is Phase 4.
select
    substr(source_sha256, 1, 12) || ':' || cast(seq as string) as shutdown_id,
    release_no,
    release_period,
    outage_date,
    circle as circle_as_printed,
    feeder_name as feeder_name_as_printed,
    start_local,
    end_local,
    start_utc,
    end_utc,
    flags,
    source_file,
    source_sha256,
    fetched_at
from {{ ref('stg_iesco_press_release_window') }}
