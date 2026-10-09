-- Census area rows kept out of dim_area_indicators: hierarchical keys that are not unique, which
-- happens only in the Sindh urban PDFs where wrapped body names were quarantined by the parser.
select
    'urban' as area_type,
    province,
    area_key,
    level as area_level,
    name as area_name,
    district,
    'ambiguous_hierarchical_key' as reason,
    population_source_sha256
from {{ ref('stg_pbs_urban') }}
where population_key_ambiguous
