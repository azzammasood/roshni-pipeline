-- Headlines are the outlets' words, linked to the original; never Roshni's reporting.
select
    link,
    outlet,
    title,
    published_at,
    first_seen_at,
    coalesce(published_at, first_seen_at) as sort_at,
    source_file,
    source_sha256
from {{ source('parsed', 'news_headline') }}
