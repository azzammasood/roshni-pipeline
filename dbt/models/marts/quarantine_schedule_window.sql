-- IESCO scenario slots kept out of fct_schedule_window, with the reason:
--   slot_count_mismatch   a feeder's level-N column does not hold exactly N one-hour slots
--   feeder_quarantined    the feeder itself is in quarantine_feeder
with slots as (
    select
        s.*,
        f.feeder_name,
        f.source_sha256,
        count(*) over (partition by s.circle, s.sheet_row, s.level_hours) as slots_at_level
    from {{ ref('stg_iesco_schedule_slot') }} as s
    inner join {{ ref('stg_iesco_feeder') }} as f
        on s.circle = f.circle and s.sheet_row = f.sheet_row
)

select
    'iesco' as source,
    s.circle,
    s.sheet_row,
    s.feeder_name,
    s.level_hours,
    s.slot_start_hour,
    s.slot_end_hour,
    case
        when q.sheet_row is not null then 'feeder_quarantined:' || q.reason
        else 'slot_count_mismatch'
    end as reason,
    s.source_sha256
from slots as s
left join {{ ref('quarantine_feeder') }} as q
    on q.source = 'iesco' and q.circle = s.circle and q.sheet_row = s.sheet_row
where q.sheet_row is not null or s.slots_at_level <> s.level_hours
