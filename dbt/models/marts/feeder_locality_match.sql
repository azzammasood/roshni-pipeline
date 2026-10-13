-- IESCO feeder -> census locality matches (auto_exact or owner-accepted), with confidence.
-- Approximate: names only, no coordinates. A feeder may serve several localities.
select
    m.subject_id as feeder_id,
    m.candidate_id as area_id,
    m.candidate_name as area_name,
    m.subject_group as circle,
    m.method,
    m.match_status,
    m.match_confidence,
    m.note as match_note
from ({{ accepted_matches('review_feeder_locality') }}) as m
