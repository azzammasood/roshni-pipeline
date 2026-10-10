-- Planned shutdowns with the IESCO feeder they refer to, where the printed name was matched
-- (auto_exact or owner-accepted). Unmatched rows keep feeder_id null and say why.
select
    s.*,
    m.candidate_id as feeder_id,
    m.match_status,
    m.match_confidence,
    case
        when m.candidate_id is not null then 'matched'
        when r.out_of_scope = 1 then 'out_of_scope'
        when r.undecided > 0 then 'pending_review'
        else 'unmatched'
    end as feeder_match_state
from {{ ref('fct_planned_shutdown') }} as s
left join ({{ accepted_matches('review_press_feeder') }}) as m
    on m.subject_group = s.circle_as_printed and m.subject_name = s.feeder_name_as_printed
left join (
    select
        subject_group,
        subject_name,
        max(case when status = 'out_of_scope' then 1 else 0 end) as out_of_scope,
        sum(case when status = 'suggested' and decision is null then 1 else 0 end) as undecided
    from {{ ref('review_press_feeder') }}
    group by subject_group, subject_name
) as r
    on r.subject_group = s.circle_as_printed and r.subject_name = s.feeder_name_as_printed
