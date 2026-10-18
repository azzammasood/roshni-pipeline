-- IESCO's announced maintenance per month (Asia/Karachi dates as printed) and listing-page row
-- (circle, GSO or construction): windows, feeders, and window hours added up. Announcements, not
-- load shedding and not measurements; first_date/last_date show which dates the files cover.
-- unique_* leave out GSO rows that repeat a circle file's window, so they add up across rows.
select
    concat(substr(cast(outage_date as string), 1, 7), ':', item) as month_item_id,
    substr(cast(outage_date as string), 1, 7) as month,
    item,
    count(*) as windows,
    count(distinct coalesce(feeder_code, feeder_name_as_printed)) as feeders,
    sum(window_minutes) / 60.0 as window_hours,
    sum(case when repeats_circle_window then 0 else 1 end) as unique_windows,
    sum(case when repeats_circle_window then 0 else window_minutes end) / 60.0
        as unique_window_hours,
    min(outage_date) as first_date,
    max(outage_date) as last_date
from {{ ref('fct_maintenance_window') }}
group by 1, 2, 3
