-- Tables 33 (population) and 34 (housing) side by side, joined on the hierarchical key only
-- where that key is unique on both sides (Sindh PDFs leave some keys ambiguous; never guess).
with pop as (
    select *, count(*) over (partition by province, area_key) as key_rows
    from {{ source('parsed', 'pbs_urban_population') }}
),

hou as (
    select *, count(*) over (partition by province, area_key) as key_rows
    from {{ source('parsed', 'pbs_urban_housing') }}
)

select
    pop.province,
    pop.area_key,
    pop.level,
    pop.name,
    pop.district,
    pop.tehsil,
    pop.body,
    pop.charge,
    pop.circle,
    pop.pop_total,
    pop.literacy_pct_total,
    pop.edu_degree_above_male + pop.edu_degree_above_female
        + pop.edu_degree_above_transgender as degree_above_total,
    hou.housing_units_total,
    hou.structure_pacca,
    hou.electricity,
    hou.avg_household_size,
    pop.key_rows > 1 as population_key_ambiguous,
    hou.area_key is null as housing_missing,
    pop.flags as population_flags,
    hou.flags as housing_flags,
    pop.source_file as population_source_file,
    pop.source_sha256 as population_source_sha256,
    hou.source_sha256 as housing_source_sha256
from pop
left join hou
    on pop.province = hou.province
    and pop.area_key = hou.area_key
    and hou.key_rows = 1
    and pop.key_rows = 1
