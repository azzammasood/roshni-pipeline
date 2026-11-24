-- Tables 33 (population) and 34 (housing) side by side, joined on the hierarchical key only
-- where that key is unique on both sides (Sindh PDFs leave some keys ambiguous; never guess).
-- The uniqueness rules are applied before the join, so the join is a plain equality join: a
-- condition on the left table inside a LEFT JOIN's ON clause made DuckDB plan a nested-loop
-- join, quadratic in rows (docs/benchmarks.md). An ambiguous population key joins on NULL,
-- which matches nothing, exactly as before.
with pop as (
    select
        *,
        case when key_rows = 1 then area_key end as join_key
    from (
        select *, count(*) over (partition by province, area_key) as key_rows
        from {{ source('parsed', 'pbs_urban_population') }}
    ) as p
),

hou as (
    select *
    from (
        select *, count(*) over (partition by province, area_key) as key_rows
        from {{ source('parsed', 'pbs_urban_housing') }}
    ) as h
    where key_rows = 1
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
    and pop.join_key = hou.area_key
