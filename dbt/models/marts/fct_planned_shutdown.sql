-- Dated planned-shutdown windows announced in IESCO press releases (announcements, not
-- measurements). Feeder and circle names are as printed; matching to dim_feeder is Phase 4.
--
-- Incremental: a press release never changes once published (each file is keyed by its
-- SHA-256), so a run on a persistent warehouse only loads windows from release files it has not
-- seen. The strategy is chosen per adapter so the model stays portable (DuckDB: delete+insert;
-- Databricks: merge). CI builds a fresh DuckDB file, which is always a full build.
{{
    config(
        materialized='incremental',
        unique_key='shutdown_id',
        incremental_strategy=('merge' if target.type == 'databricks' else 'delete+insert'),
        on_schema_change='append_new_columns'
    )
}}

select
    substr(source_sha256, 1, 12) || ':' || cast(seq as string) as shutdown_id,
    release_no,
    release_period,
    outage_date,
    circle as circle_as_printed,
    feeder_name as feeder_name_as_printed,
    start_local,
    end_local,
    start_utc,
    end_utc,
    flags,
    source_file,
    source_sha256,
    fetched_at
from {{ ref('stg_iesco_press_release_window') }}
{% if is_incremental() %}
where source_sha256 not in (select distinct source_sha256 from {{ this }})
{% endif %}
