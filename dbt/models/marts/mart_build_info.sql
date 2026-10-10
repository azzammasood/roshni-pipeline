-- When this warehouse build ran (UTC). Used as last_updated when a source has no fetch time.
select current_timestamp as built_at
