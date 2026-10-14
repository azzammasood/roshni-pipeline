-- Load-shedding hours as REPORTED TO NEPRA by each distribution company (not measured).
select
    concat(company, ':', fiscal_year, ':', source_sha256) as observation_id,
    company,
    fiscal_year,
    report_year,
    reported_hours_per_day,
    line,
    source_file,
    source_sha256,
    fetched_at
from {{ source('parsed', 'nepra_load_shedding') }}
