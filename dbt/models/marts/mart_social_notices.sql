-- Notices IESCO posted on Facebook, recorded by hand (seed iesco_social_notices). Each row links
-- to the post; summaries are ours. Notices, not measurements.
select
    notice_id,
    platform,
    posted_on,
    url,
    kind,
    circle,
    areas,
    window_date,
    start_local,
    end_local,
    summary,
    added_by,
    added_on
from {{ ref('iesco_social_notices') }}
