-- Match K-Electric listed feeders to schedule rows on the normalised name.
-- 1. exact: identical normalised names (auto-accepted, confidence 1.0).
-- 2. truncated_name: the schedule name is a prefix (>= 20 chars) of exactly one unmatched listed
--    name and vice versa. Covers the schedule's cut-off "NAVY HOUSING SCHEME (Ex. PAKISTAN NAVY
--    HOUSING SCHEM". Recorded rule, owner-reviewed (docs/data-audit.md section 3), confidence 0.95.
with list_rows as (
    select feeder_name_norm from {{ ref('stg_ke_feeder_list') }}
),

sched_rows as (
    select feeder_name_norm from {{ ref('stg_ke_schedule') }}
),

exact as (
    select
        l.feeder_name_norm as list_name_norm,
        s.feeder_name_norm as schedule_name_norm,
        'exact' as match_method,
        1.0 as match_confidence
    from list_rows as l
    inner join sched_rows as s on l.feeder_name_norm = s.feeder_name_norm
),

prefix_candidates as (
    select
        l.feeder_name_norm as list_name_norm,
        s.feeder_name_norm as schedule_name_norm
    from list_rows as l
    inner join sched_rows as s
        on l.feeder_name_norm like s.feeder_name_norm || '%'
        and l.feeder_name_norm <> s.feeder_name_norm
    where length(s.feeder_name_norm) >= 20
        and l.feeder_name_norm not in (select list_name_norm from exact)
        and s.feeder_name_norm not in (select schedule_name_norm from exact)
),

prefix_unique as (
    select
        list_name_norm,
        schedule_name_norm,
        count(*) over (partition by list_name_norm) as n_for_list,
        count(*) over (partition by schedule_name_norm) as n_for_schedule
    from prefix_candidates
)

select * from exact
union all
select
    list_name_norm,
    schedule_name_norm,
    'truncated_name' as match_method,
    0.95 as match_confidence
from prefix_unique
where n_for_list = 1 and n_for_schedule = 1
