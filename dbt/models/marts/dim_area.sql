-- Every area the project can show: census areas, K-Electric IBC areas, IESCO circles.
-- geometry_wkt is null until an approved boundary source exists (docs/boundary-research.md);
-- until then the product uses ranked lists and charts, no map.
select
    area_id,
    area_name as name,
    area_type || '_' || area_level as level,
    'pbs_census_2023' as source,
    province,
    district as parent_name,
    cast(null as string) as geometry_wkt
from {{ ref('dim_area_indicators') }}

union all

select distinct
    'ke_ibc:' || ibc as area_id,
    ibc as name,
    'kelectric_ibc' as level,
    'kelectric_feeder_list' as source,
    'sindh' as province,
    'Karachi (K-Electric territory)' as parent_name,
    cast(null as string) as geometry_wkt
from {{ ref('dim_feeder') }}
where source = 'kelectric' and ibc is not null

union all

select distinct
    'iesco_circle:' || circle as area_id,
    circle as name,
    'iesco_circle' as level,
    'iesco_schedule_xlsx' as source,
    case when circle = 'islamabad' then 'islamabad' when circle = 'ajk' then 'ajk'
        else 'punjab' end as province,
    'IESCO territory' as parent_name,
    cast(null as string) as geometry_wkt
from {{ ref('dim_feeder') }}
where source = 'iesco'
