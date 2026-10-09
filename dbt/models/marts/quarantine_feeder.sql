-- Feeder rows kept out of dim_feeder, with the reason. Known anomalies are flagged here, not fixed:
--   non_numeric_code                 code printed as text (e.g. "NOT ALLOTED"): no join key
--   other_disco_feeder_sharing_code  a feeder labelled "(FESCO)" that reuses an IESCO code
--   duplicate_code_in_circle         any other repeated circle + code (both rows held back)
with iesco as (
    select
        *,
        case when upper(feeder_name) like '%(FESCO)%' then 1 else 0 end as is_other_disco
    from {{ ref('stg_iesco_feeder') }}
),

counted as (
    select
        *,
        count(*) over (partition by circle, feeder_code) as rows_with_code,
        sum(is_other_disco) over (partition by circle, feeder_code) as other_disco_rows
    from iesco
),

classified as (
    select
        *,
        case
            when feeder_code is null then 'non_numeric_code'
            when rows_with_code > 1 and is_other_disco = 1 then 'other_disco_feeder_sharing_code'
            when rows_with_code > 1 and other_disco_rows = 0 then 'duplicate_code_in_circle'
        end as reason
    from counted
)

select
    'iesco' as source,
    circle,
    sheet_row,
    feeder_name,
    feeder_code_raw,
    reason,
    source_file,
    source_sha256
from classified
where reason is not null
