-- IESCO planned shutdowns announced in press releases, per month (Asia/Karachi dates as printed)
-- and circle: windows, summed window hours (one feeder's window counts once per feeder), and
-- releases. These are announced maintenance shutdowns, not load shedding and not measurements.
-- first_date/last_date show how much of the month the collected releases cover.
select
    concat(substr(cast(m.outage_date as varchar), 1, 7), ':', circle_as_printed) as month_circle_id,
    substr(cast(outage_date as varchar), 1, 7) as month,
    circle_as_printed as circle,
    count(*) as windows,
    sum(case when m.end_min > m.start_min then m.end_min - m.start_min
             else m.end_min + 1440 - m.start_min end) / 60.0 as window_hours,
    count(distinct concat(release_period, '#', release_no)) as releases,
    min(outage_date) as first_date,
    max(outage_date) as last_date
from (
    select
        s.*,
        cast(substr(s.start_local, 1, 2) as integer) * 60
        + cast(substr(s.start_local, 4, 2) as integer) as start_min,
        cast(substr(s.end_local, 1, 2) as integer) * 60
        + cast(substr(s.end_local, 4, 2) as integer) as end_min
    from {{ ref('fct_planned_shutdown') }} as s
) as m
group by 1, 2, 3
