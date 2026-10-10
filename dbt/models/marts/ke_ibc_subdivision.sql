-- K-Electric IBC area -> Karachi census sub-division crosswalk. Only owner-accepted rows count
-- (the name-based draft is never auto-accepted). Out-of-scope IBCs (Uthal) are listed as such.
select
    subject_id as ibc,
    candidate_id as subdivision_area_id,
    candidate_name as subdivision_name,
    'accepted' as crosswalk_status,
    score / 100.0 as name_similarity
from {{ ref('review_ibc_subdivision') }}
where decision = 'accepted' and candidate_id is not null

union all

select
    subject_id as ibc,
    cast(null as string) as subdivision_area_id,
    cast(null as string) as subdivision_name,
    'out_of_scope' as crosswalk_status,
    cast(null as double) as name_similarity
from {{ ref('review_ibc_subdivision') }}
where status = 'out_of_scope'
