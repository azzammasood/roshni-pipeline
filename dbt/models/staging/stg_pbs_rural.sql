-- Tables 31 (population) and 32 (housing) joined on the hierarchical key (unique per GE suite).
select
    pop.province,
    pop.area_key,
    pop.level,
    pop.name,
    pop.hadbast,
    pop.district,
    pop.tehsil,
    pop.qh,
    pop.pc,
    pop.pop_total,
    pop.literacy_pct_total,
    pop.edu_degree_above_male + pop.edu_degree_above_female
        + pop.edu_degree_above_transgender as degree_above_total,
    pop.area_acres,
    hou.housing_units_total,
    hou.structure_pacca,
    hou.electricity,
    hou.avg_household_size,
    hou.area_key is null as housing_missing,
    pop.flags as population_flags,
    hou.flags as housing_flags,
    pop.source_file as population_source_file,
    pop.source_sha256 as population_source_sha256,
    hou.source_sha256 as housing_source_sha256
from {{ source('parsed', 'pbs_rural_population') }} as pop
left join {{ source('parsed', 'pbs_rural_housing') }} as hou
    on pop.area_key = hou.area_key
