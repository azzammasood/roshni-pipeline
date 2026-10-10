-- A feeder-locality pair is listed once.
select feeder_id, area_id, count(*) as n
from {{ ref('feeder_locality_match') }}
group by feeder_id, area_id
having count(*) > 1
