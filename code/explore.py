"""Diagnostics: verify classification assumptions before the real analysis."""
import json
from collections import Counter

import geopandas as gpd

DATA = "/home/hatch/workspace/denver-housing-permits/data"
V = "/home/hatch/workspace/denver-housing-permits/.venv/bin/python"

permits = gpd.read_file(f"{DATA}/permits_2020.geojson")
print("permits rows:", len(permits))
print("CRS:", permits.crs)

# (0,0) junk locations
geom = permits.geometry
zero = ((geom.x == 0) & (geom.y == 0)).sum()
print("at (0,0):", zero)
null_geom = geom.is_empty.sum() + geom.isna().sum()
print("empty/na geom:", null_geom)

# date range
permits["d"] = gpd.pd.to_datetime(permits["DATE_ISSUED"], unit="ms", utc=True)
print("date min:", permits["d"].min(), "max:", permits["d"].max())

# cancelled
canc = permits["CANCEL"].notna().sum()
print("cancelled:", canc)

# ADU signal hunt
for col in ["ADDRESS", "CLASS"]:
    s = permits[col].fillna("").str.upper()
    print(f"ADU mention in {col}:", s.str.contains("ADU").sum())
    print(f"  'ACCESSORY' in {col}:", s.str.contains("ACCESSOR").sum())

# CLASS x STAT_CODE_1 crosstab (top)
print("\nCLASS x STAT_CODE_1:")
ct = Counter(zip(permits["CLASS"].fillna("?"), permits["STAT_CODE_1"].fillna("?")))
for (c, s), n in ct.most_common(25):
    print(f"  {c} / {s}: {n}")

# NEIGHBORHOOD field coverage
print("\nNEIGHBORHOOD null:", permits["NEIGHBORHOOD"].isna().sum())
print("distinct NEIGHBORHOOD:", permits["NEIGHBORHOOD"].nunique())

# zoning district classification preview
zoning = gpd.read_file(f"{DATA}/zoning.geojson")
zd = zoning["ZONE_DISTRICT"].fillna("")
su = zd.str.contains("SU", na=False)
print("\nzoning polygons:", len(zoning))
print("SU districts:", su.sum())
print("SU district names:", sorted(zd[su].unique())[:40])
