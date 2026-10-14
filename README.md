# Where Denver Builds (and Where It Doesn't)

A data brief on residential construction geography in Denver, Colorado: 30,902 permits issued 2020-2026 mapped against the city's zoning, its own Blueprint Denver growth plan, and RTD rail stations.

**Headline:** Denver's comprehensive plan says to grow in centers, corridors, and near transit. Three-quarters of new residential construction happened outside the city's own designated growth areas, four in five more than half a mile from rail - and new construction volume has fallen by more than half since 2021.

Read the full brief: [brief/denver-housing-permits-brief.md](brief/denver-housing-permits-brief.md)

## Contents

- `brief/` - the narrative brief with findings, charts, methods, and caveats
- `charts/` - 7 charts (PNG)
- `data/` - aggregated statistics (CSV/JSON) plus feature-layer-ready GeoJSONs:
  - `permits_enriched.geojson` - one row per permit with joined attributes (neighborhood, zoning district, single-unit-only flag, growth-area status and type, transit-buffer flag). Publish directly as an ArcGIS feature layer.
  - `neighborhoods_summary.geojson` - per-neighborhood aggregates with polygons
- `code/` - download scripts and analysis (`download.py`, `analyze.py`, `explore.py`)

## Data sources

All public:

- Residential Construction Permits - City and County of Denver, ArcGIS Hub (`ODC_DEV_RESIDENTIALCONSTPERMIT_P`), 31,170 issued 2020-01-02 through 2026-10-08
- Zoning - City and County of Denver, ArcGIS Hub (`ODC_ZONE_ZONING_A`), 3,777 polygons
- Blueprint Denver Future Places - City and County of Denver, ArcGIS Hub (`ODC_PLAN_BPFUTUREPLACES_A`)
- Statistical Neighborhoods - City and County of Denver, ArcGIS Hub (`ODC_ADMN_NEIGHBORHOOD_A`), 78 polygons
- RTD rail stations - derived from RTD's public GTFS feed (67 stations serving rail routes)

## Reproduce

1. Download the five layers above (Denver: https://denvergov.org/opendata; RTD GTFS: https://www.rtd-denver.com/)
2. Run `python code/download.py` (or place files in `data/`)
3. Run `python code/analyze.py`
4. Charts land in `output/charts/`; enriched layers in `output/`

Requires Python 3 with geopandas, shapely, matplotlib.

## Methods and data

The public layers listed under Data sources are downloaded with [code/download.py](code/download.py) and analyzed with [code/analyze.py](code/analyze.py). Aggregate outputs are in [data/stats.json](data/stats.json) and the CSV and GeoJSON files in [data/](data/). The [full brief](brief/denver-housing-permits-brief.md) contains the methods and caveats.

## Part of Machine Readable

This brief is part of [Machine Readable](https://adowlen.github.io/machine-readable/), the catalog of all Machine Readable briefs.


## Reuse and citation

This brief is free to cite, quote, and reuse under the CC BY 4.0 license (see LICENSE). If you use it, please credit Machine Readable and link back to this repository.

Attribution line: Machine Readable (Alex Dowlen), https://github.com/adowlen/denver-housing-permits-data-brief
