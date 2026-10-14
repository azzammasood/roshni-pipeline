-- K-Electric schedule versions with their effective dates (source_documents seed, by SHA-256).
-- A version without a seed row has no effective date and is left out (publish already stops when
-- the current file has none). Schedules, not measurements.
select
    v.source_sha256,
    v.source_file,
    d.effective_from,
    v.feeders,
    v.avg_scheduled_minutes,
    v.avg_scheduled_minutes / 60.0 as avg_scheduled_hours
from {{ source('parsed', 'kelectric_schedule_version') }} as v
inner join {{ ref('source_documents') }} as d on v.source_sha256 = d.source_sha256
