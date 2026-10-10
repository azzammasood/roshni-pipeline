{% macro accepted_matches(review_seed) %}
-- Rows of a review seed that count as matches: auto_exact unless the owner rejected it, or
-- anything the owner accepted. Everything else (suggested, no_candidate, ...) is not a match.
select
    subject_id,
    subject_name,
    subject_group,
    candidate_id,
    candidate_name,
    score,
    method,
    case when decision = 'accepted' then 'accepted' else 'auto_exact' end as match_status,
    score / 100.0 as match_confidence
from {{ ref(review_seed) }}
where candidate_id is not null
    and (
        decision = 'accepted'
        or (status = 'auto_exact' and coalesce(decision, '') <> 'rejected')
    )
{% endmacro %}
