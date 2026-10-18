-- One row per announced IESCO maintenance window: the same feeder, date and time printed in
-- several stored versions of a workbook counts once (kept from the newest file). Feeders are
-- linked to dim_feeder by their 6-digit code (codes are unique across IESCO); unlinked rows keep
-- the names as printed. The GSO (grid stations) file restates many windows that a circle's
-- file also prints; such rows keep their place (each file's figures stay as printed) and
-- carry repeats_circle_window, so unique totals count each window once.
-- Announcements, not load shedding and not measurements.
with ranked as (
    select
        w.*,
        coalesce(w.feeder_code, upper(w.feeder_name)) as feeder_key,
        row_number() over (
            partition by w.item, coalesce(w.feeder_code, upper(w.feeder_name)),
                w.outage_date, w.start_local, w.end_local
            order by w.fetched_at desc, w.source_sha256 desc, w.sheet_row
        ) as version_rank
    from {{ ref('stg_iesco_maintenance_window') }} as w
),

circle_windows as (
    select distinct feeder_code, outage_date, start_local, end_local
    from ranked
    where version_rank = 1 and item not in ('gso', 'construction') and feeder_code is not null
),

feeders as (
    select feeder_id, feeder_code from {{ ref('dim_feeder') }} where source = 'iesco'
)

select
    concat(
        r.item, ':', r.feeder_key, ':', cast(r.outage_date as string), ':', r.start_local, '-',
        r.end_local
    ) as window_id,
    r.item,
    f.feeder_id,
    r.feeder_code,
    r.feeder_name as feeder_name_as_printed,
    r.circle_as_printed,
    r.division,
    r.subdivision,
    r.grid as grid_as_printed,
    r.outage_date,
    r.start_local,
    r.end_local,
    r.start_utc,
    r.end_utc,
    (cast(substr(r.end_local, 1, 2) as integer) * 60 + cast(substr(r.end_local, 4, 2) as integer))
    - (cast(substr(r.start_local, 1, 2) as integer) * 60 + cast(substr(r.start_local, 4, 2) as integer))
        as window_minutes,
    r.purpose,
    r.area_affected,
    (r.item = 'gso' and c.feeder_code is not null) as repeats_circle_window,
    r.flags,
    r.source_file,
    r.source_sha256,
    r.fetched_at
from ranked as r
left join feeders as f on f.feeder_code = r.feeder_code
left join circle_windows as c
    on c.feeder_code = r.feeder_code and c.outage_date = r.outage_date
    and c.start_local = r.start_local and c.end_local = r.end_local
where r.version_rank = 1
