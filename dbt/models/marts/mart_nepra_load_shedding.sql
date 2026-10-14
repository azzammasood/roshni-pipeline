-- One value per company and fiscal year: average daily load-shedding hours as REPORTED TO NEPRA
-- by the company (NEPRA says several companies under-report; never call these measurements).
-- Chosen value: the earliest report that lists the year (normally that year's own report). Later
-- reports restate it; any restatement that differs by more than 0.01 h is flagged, never fixed.
with obs as (
    select * from {{ ref('stg_nepra_load_shedding') }}
),

ranked as (
    select
        obs.*,
        row_number() over (
            partition by company, fiscal_year order by report_year, fetched_at desc
        ) as rank_in_cell
    from obs
),

spread as (
    select
        company,
        fiscal_year,
        count(*) as reports,
        min(reported_hours_per_day) as min_reported,
        max(reported_hours_per_day) as max_reported
    from obs
    group by company, fiscal_year
)

select
    concat(r.company, ':', r.fiscal_year) as company_year_id,
    r.company,
    r.fiscal_year,
    r.reported_hours_per_day,
    r.report_year as chosen_report_year,
    r.source_file as chosen_source_file,
    r.source_sha256 as chosen_source_sha256,
    s.reports,
    s.min_reported,
    s.max_reported,
    (s.max_reported - s.min_reported) > 0.01 as values_disagree
from ranked as r
inner join spread as s on r.company = s.company and r.fiscal_year = s.fiscal_year
where r.rank_in_cell = 1
