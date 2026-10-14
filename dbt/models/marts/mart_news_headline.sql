-- Latest load-shedding headlines for the home page, newest first, at most 12, however old the
-- newest one is (owner, 2026-10-14: when there is no news today, show the latest whenever it was).
with ranked as (
    select
        h.*,
        row_number() over (order by h.sort_at desc, h.link) as recency
    from {{ ref('stg_news_headline') }} as h
)

select link, outlet, title, published_at, first_seen_at, recency
from ranked
where recency <= 12
