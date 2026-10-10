# Boundary research (Phase 4, 2026-10-10)

Question: is there a **legally usable** polygon source for (a) Karachi's 28 census sub-divisions or K-Electric's 30 IBC areas, and (b) IESCO towns and localities? **No source has been added.** `dim_area.geometry_wkt` stays null; v1 uses ranked lists and charts, no map.

## Findings

| Source | Levels | Licence | Fit |
|---|---|---|---|
| OCHA COD-AB Pakistan on HDX (`cod-ab-pak`, WFP SDI) | ADM1 provinces (7), ADM2 districts (160), ADM3 tehsils (577) | Creative Commons Attribution for Intergovernmental Organisations (CC BY-IGO); attribution required | Good for **district/tehsil** maps of the IESCO districts. Last reviewed Sep 2024, files dated Sep 2022, and metadata says it "requires improvements". Probably predates Karachi's 2023 sub-divisions (unverified). No IBC areas, no mauzas. |
| geoBoundaries Pakistan (also on HDX) | ADM0 to ADM3, 2017 to 2019, partly from OSM | CC BY 4.0 (stated for country datasets) | Same levels as COD-AB, older. Inherits OSM terms where derived from it: check per-level metadata before use. |
| OpenStreetMap | Admin relations exist for Pakistan; coverage at Karachi sub-division level **not verified** (two Overpass queries failed with 504/500 on 2026-10-10; not retried, to stay polite) | ODbL 1.0: attribution "© OpenStreetMap contributors"; a **publicly used derived database must be shared under ODbL** (share-alike) | Possible for Karachi if relations exist; share-alike applies to any published boundary layer we derive. |
| urckarachi.org district maps | Images of 2017 districts/towns | Not stated | **Not usable**: images only, no licence, not authoritative. |
| K-Electric IBC areas | none published as polygons | n/a | No source found. IBC areas are utility billing areas, not census units. |
| IESCO towns / localities, PBS mauzas | none found as public polygons | n/a | No source found. PBS publishes tables, not mauza boundaries. |

## Recommendation
1. **v1: no map** (brief fallback). Ranked lists and charts by IBC, sub-division and district.
2. If a map is wanted later: a **district/tehsil map from COD-AB** (CC BY-IGO, attribution) is the lowest-risk option for the IESCO side. Owner approval needed before adding it as a source.
3. For Karachi sub-divisions: verify OSM coverage when Overpass is available. If the boundaries exist, adopting them means accepting ODbL share-alike for the published boundary layer. Owner decision.
4. IBC areas and mauzas stay non-spatial.

## Sources
- [HDX: Pakistan – Subnational Administrative Boundaries (cod-ab-pak)](https://data.humdata.org/dataset/cod-ab-pak)
- [geoBoundaries country downloads](https://www.geoboundaries.org/countryDownloads.html)
- [OpenStreetMap copyright and licence](https://www.openstreetmap.org/copyright)
- [urckarachi.org: Karachi district maps](https://urckarachi.org/karachi-district-maps-complete/)
