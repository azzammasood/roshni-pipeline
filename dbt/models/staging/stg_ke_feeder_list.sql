select
    serial,
    feeder_name,
    feeder_name_norm,
    ibc,
    atc_loss_pct,
    category,
    page,
    source_file,
    source_sha256,
    fetched_at
from {{ source('parsed', 'kelectric_feeder_list') }}
