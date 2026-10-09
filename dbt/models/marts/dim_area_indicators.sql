-- PBS Census 2023 indicators per area. Urban: district > tehsil > body > charge > circle.
-- Rural: district > tehsil > QH > PC > mauza. Shares only where the denominator is positive.
-- Gas connection is deliberately excluded: it is not a wealth proxy (many towns lack a network).
with urban as (
    select
        'pbs_urban:' || province || ':' || area_key as area_id,
        'urban' as area_type,
        province,
        level as area_level,
        name as area_name,
        district,
        tehsil as subdivision,
        body as urban_body,
        cast(null as string) as hadbast,
        pop_total,
        housing_units_total,
        literacy_pct_total,
        degree_above_total,
        structure_pacca,
        electricity,
        avg_household_size,
        housing_missing,
        population_key_ambiguous as key_ambiguous,
        population_flags,
        housing_flags,
        population_source_sha256,
        housing_source_sha256
    from {{ ref('stg_pbs_urban') }}
),

rural as (
    select
        'pbs_rural:' || province || ':' || area_key as area_id,
        'rural' as area_type,
        province,
        level as area_level,
        name as area_name,
        district,
        tehsil as subdivision,
        cast(null as string) as urban_body,
        hadbast,
        pop_total,
        housing_units_total,
        literacy_pct_total,
        degree_above_total,
        structure_pacca,
        electricity,
        avg_household_size,
        housing_missing,
        false as key_ambiguous,
        population_flags,
        housing_flags,
        population_source_sha256,
        housing_source_sha256
    from {{ ref('stg_pbs_rural') }}
),

unioned as (
    select * from urban
    union all
    select * from rural
)

select
    area_id,
    area_type,
    province,
    area_level,
    area_name,
    district,
    subdivision,
    urban_body,
    hadbast,
    pop_total,
    housing_units_total,
    literacy_pct_total as literacy_pct,
    case when pop_total > 0 then 100.0 * degree_above_total / pop_total end as degree_share_pct,
    case
        when housing_units_total > 0 then 100.0 * structure_pacca / housing_units_total
    end as pacca_share_pct,
    case
        when housing_units_total > 0 then 100.0 * electricity / housing_units_total
    end as electricity_share_pct,
    avg_household_size,
    housing_missing,
    population_flags,
    housing_flags,
    population_source_sha256,
    housing_source_sha256
from unioned
where not key_ambiguous
