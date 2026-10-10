-- Match rates per task and group (IESCO circle, press-release circle, IBC). One subject counts
-- once, by its best state: matched > pending review > no candidate > out of scope.
with reviews as (
    select 'feeder_locality' as task, * from {{ ref('review_feeder_locality') }}
    union all
    select 'press_feeder' as task, * from {{ ref('review_press_feeder') }}
    union all
    select 'ibc_subdivision' as task, * from {{ ref('review_ibc_subdivision') }}
),

per_subject as (
    select
        task,
        subject_group,
        subject_id,
        max(case
            when decision = 'accepted' then 4
            when status = 'auto_exact' and coalesce(decision, '') <> 'rejected' then 4
            when status = 'suggested' and decision is null then 3
            when status = 'out_of_scope' then 1
            else 2
        end) as state
    from reviews
    group by task, subject_group, subject_id
)

select
    task,
    subject_group,
    count(*) as subjects,
    sum(case when state = 4 then 1 else 0 end) as matched,
    sum(case when state = 3 then 1 else 0 end) as pending_review,
    sum(case when state = 2 then 1 else 0 end) as unmatched,
    sum(case when state = 1 then 1 else 0 end) as out_of_scope,
    round(100.0 * sum(case when state = 4 then 1 else 0 end)
        / nullif(sum(case when state <> 1 then 1 else 0 end), 0), 1) as matched_pct_in_scope
from per_subject
group by task, subject_group
