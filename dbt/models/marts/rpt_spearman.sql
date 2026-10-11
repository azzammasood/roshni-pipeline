-- Exploratory Spearman rank correlations (average ranks for ties, then Pearson on ranks).
-- Descriptive only: small n, no significance claimed, no causal reading. n is always reported.
--   subdivision: share of listed feeders at 12 h vs census indicators, per sub-division
--   feeder:      ATC loss vs scheduled hours, per listed K-Electric feeder
with sub as (
    select * from {{ ref('mart_ke_subdivision_equity') }}
),

pairs as (
    select 'subdivision' as unit, 'share_12h_pct' as y_name, 'literacy_pct' as x_name,
           share_12h_pct as y, literacy_pct as x from sub
    union all
    select 'subdivision', 'share_12h_pct', 'degree_share_pct', share_12h_pct, degree_share_pct
    from sub
    union all
    select 'subdivision', 'share_12h_pct', 'pacca_share_pct', share_12h_pct, pacca_share_pct
    from sub
    union all
    select 'subdivision', 'share_12h_pct', 'avg_household_size', share_12h_pct, avg_household_size
    from sub
    union all
    select 'subdivision', 'share_12h_pct', 'mean_atc_loss_pct', share_12h_pct, mean_atc_loss_pct
    from sub
    union all
    select 'feeder', 'scheduled_hours_per_day', 'atc_loss_pct', scheduled_hours_per_day,
           atc_loss_pct
    from {{ ref('mart_ke_feeder_hours') }}
),

complete as (
    select * from pairs where x is not null and y is not null
),

ranked as (
    select
        unit, y_name, x_name,
        rank() over (partition by unit, y_name, x_name order by x)
            + (count(*) over (partition by unit, y_name, x_name, x) - 1) / 2.0 as rx,
        rank() over (partition by unit, y_name, x_name order by y)
            + (count(*) over (partition by unit, y_name, x_name, y) - 1) / 2.0 as ry
    from complete
)

select
    unit,
    y_name,
    x_name,
    count(*) as n,
    round(corr(rx, ry), 3) as spearman_rho
from ranked
group by unit, y_name, x_name
