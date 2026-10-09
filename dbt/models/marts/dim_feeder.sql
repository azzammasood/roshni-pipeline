-- One row per feeder across both utilities. IESCO keyed by circle + 6-digit code; K-Electric by
-- normalised name (listed name where matched). Geography is area-level only (no coordinates).
with iesco as (
    select f.*
    from {{ ref('stg_iesco_feeder') }} as f
    left join {{ ref('quarantine_feeder') }} as q
        on q.source = 'iesco' and q.circle = f.circle and q.sheet_row = f.sheet_row
    where q.sheet_row is null
),

ke_list as (
    select * from {{ ref('stg_ke_feeder_list') }}
),

ke_sched as (
    select * from {{ ref('stg_ke_schedule') }}
),

ke_join as (
    select * from {{ ref('int_ke_feeder_join') }}
)

select
    'iesco:' || i.circle || ':' || i.feeder_code as feeder_id,
    'iesco' as source,
    i.feeder_name,
    i.feeder_code,
    i.circle,
    i.grid_name,
    cast(null as string) as ibc,
    cast(null as string) as category,
    cast(null as double) as atc_loss_pct,
    cast(null as boolean) as in_feeder_list,
    true as has_schedule,
    cast(null as string) as schedule_match_method,
    cast(null as double) as schedule_match_confidence,
    i.flags,
    i.source_file,
    i.source_sha256,
    i.fetched_at
from iesco as i

union all

select
    'ke:' || l.feeder_name_norm as feeder_id,
    'kelectric' as source,
    l.feeder_name,
    cast(null as string) as feeder_code,
    cast(null as string) as circle,
    s.grid as grid_name,
    l.ibc,
    l.category,
    l.atc_loss_pct,
    true as in_feeder_list,
    j.schedule_name_norm is not null as has_schedule,
    j.match_method as schedule_match_method,
    j.match_confidence as schedule_match_confidence,
    case when j.schedule_name_norm is null then 'no_schedule_row' else '' end as flags,
    l.source_file,
    l.source_sha256,
    l.fetched_at
from ke_list as l
left join ke_join as j on l.feeder_name_norm = j.list_name_norm
left join ke_sched as s on j.schedule_name_norm = s.feeder_name_norm

union all

select
    'ke:' || s.feeder_name_norm as feeder_id,
    'kelectric' as source,
    s.feeder_name,
    cast(null as string) as feeder_code,
    cast(null as string) as circle,
    s.grid as grid_name,
    cast(null as string) as ibc,
    cast(null as string) as category,
    cast(null as double) as atc_loss_pct,
    false as in_feeder_list,
    true as has_schedule,
    cast(null as string) as schedule_match_method,
    cast(null as double) as schedule_match_confidence,
    'schedule_only_not_in_list' as flags,
    s.source_file,
    s.source_sha256,
    s.fetched_at
from ke_sched as s
where s.feeder_name_norm not in (select schedule_name_norm from ke_join)
