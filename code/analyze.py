"""Machine Readable day-2 analysis: Denver residential construction permits 2020-2026.

Thesis: is Denver building the right housing in the right places?
Layers: permits x zoning x Blueprint Denver growth areas x RTD rail stations x neighborhoods.

Classification rules (documented, see brief for caveats):
- CLASS normalized to upper case (source mixes 'NEW BUILDING' and 'New Building').
- new_building: NEW BUILDING, 1 - NEW BUILDING
- addition: ADDITION, 2 - ADDITION TO BUILDING
- alteration: ALTERATION/TENANT FINISH, REPAIR/REPLACE
- phased: PHASED CONSTRUCTION (large new projects built in phases -> new supply pipeline)
- site_prep: FOUNDATION ONLY/EXCAVATION variants
- non_building: NEW NON-BUILDING STRUCTURE (excluded from housing counts)
- admin: CHANGE OF CONTRACTOR, MOVE, WRECK variants, SPECIAL EVENT (excluded)
- change_of_use: CHANGE OF USE ONLY (kept separate; can add units via conversion)
- ADU flag: ADDRESS contains 'ADU' (verified sample: '... ST ADU', '... DADU')
- Cancelled permits (CANCEL not null) excluded from counts, reported separately.
- UNITS field is 72% null -> analysis uses permit counts, not unit sums (caveat).
- Single-unit-only zoning: ZONE_USE_FORM == 'SU'.
- Growth area: Blueprint GROWTH_FUTURE != 'All other areas of the city'.
- Near transit: within 0.5 mile (804.67 m) of an RTD rail station.
"""
import json
from collections import Counter

import geopandas as gpd
import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

DATA = "/home/hatch/workspace/denver-housing-permits/data"
OUT = "/home/hatch/workspace/denver-housing-permits/output"
CH = f"{OUT}/charts"

CLASS_MAP = {
    "NEW BUILDING": "new_building",
    "1 - NEW BUILDING": "new_building",
    "ADDITION": "addition",
    "2 - ADDITION TO BUILDING": "addition",
    "ALTERATION/TENANT FINISH": "alteration",
    "REPAIR/REPLACE": "alteration",
    "PHASED CONSTRUCTION": "phased",
    "FOUNDATION ONLY/EXCAVATION": "site_prep",
    "FOUNDATION ONLY/ EXCAVATION": "site_prep",
    "NEW NON-BUILDING STRUCTURE": "non_building",
    "CHANGE OF CONTRACTOR": "admin",
    "MOVE": "admin",
    "WRECK": "admin",
    "6 - WRECK": "admin",
    "SPECIAL EVENT": "admin",
    "CHANGE OF USE ONLY": "change_of_use",
}

M = 804.672  # half mile in meters
PROJ = "EPSG:26913"


def main():
    import os
    os.makedirs(CH, exist_ok=True)

    permits = gpd.read_file(f"{DATA}/permits_2020.geojson")
    print("loaded", len(permits))
    permits = permits[~permits.geometry.is_empty & permits.geometry.notna()].copy()
    print("after geom drop", len(permits))
    permits["date"] = pd.to_datetime(permits["DATE_ISSUED"], unit="ms", utc=True).dt.tz_convert("America/Denver")
    permits["ym"] = permits["date"].dt.to_period("M")
    permits["cls"] = permits["CLASS"].fillna("").str.upper().map(CLASS_MAP).fillna("other")
    unmapped = permits.loc[permits["cls"] == "other", "CLASS"].unique()
    print("unmapped CLASS values:", unmapped)
    permits["is_adu"] = permits["ADDRESS"].fillna("").str.upper().str.contains("ADU")
    permits["cancelled"] = permits["CANCEL"].notna()

    stats = {}
    stats["total_permits_2020"] = len(permits)
    stats["cancelled"] = int(permits["cancelled"].sum())
    act = permits[~permits["cancelled"]].copy()
    stats["active_permits"] = len(act)
    stats["by_class"] = {k: int(v) for k, v in act["cls"].value_counts().items()}
    stats["adu_permits"] = int(act["is_adu"].sum())
    stats["adu_new_building"] = int(((act["is_adu"]) & (act["cls"] == "new_building")).sum())

    # ---- time series ----
    ts = act[act["cls"].isin(["new_building", "phased", "site_prep", "addition", "alteration"])]
    monthly = ts.groupby(["ym", "cls"]).size().unstack(fill_value=0)
    monthly.index = monthly.index.to_timestamp()
    monthly.to_csv(f"{OUT}/monthly_permits_by_class.csv")

    # new construction monthly (new_building + phased + site_prep)
    nc = monthly[["new_building", "phased", "site_prep"]].sum(axis=1)
    stats["new_construction_monthly_avg_2020_2021"] = round(float(nc["2020":"2021"].mean()), 1)
    stats["new_construction_monthly_avg_2022"] = round(float(nc["2022"].mean()), 1)
    stats["new_construction_monthly_avg_2023"] = round(float(nc["2023"].mean()), 1)
    stats["new_construction_monthly_avg_2024"] = round(float(nc["2024"].mean()), 1)
    stats["new_construction_monthly_avg_2025"] = round(float(nc["2025"].mean()), 1)
    stats["new_construction_monthly_avg_2026_ytd"] = round(float(nc["2026"].mean()), 1)

    # ---- spatial joins ----
    print("projecting + spatial joins...")
    act_p = act.to_crs(PROJ)
    zoning = gpd.read_file(f"{DATA}/zoning.geojson").to_crs(PROJ)
    bp = gpd.read_file(f"{DATA}/bp_growth_areas.geojson").to_crs(PROJ)
    nbhd = gpd.read_file(f"{DATA}/neighborhoods.geojson").to_crs(PROJ)
    stations = gpd.read_file(f"{DATA}/rtd_rail_stations.geojson").to_crs(PROJ)

    act["zone_district"] = None
    act["zone_use_form"] = None
    act["single_unit_zoning"] = False
    act["in_growth_area"] = False
    act["growth_future"] = None
    act["plctype_fut"] = None
    act["near_transit_halfmi"] = False
    act["nbhd_spatial"] = None

    # zoning join
    j = gpd.sjoin(act_p, zoning[["ZONE_DISTRICT", "ZONE_USE_FORM", "geometry"]], how="left", predicate="within")
    # dedupe: keep first match per permit
    j = j[~j.index.duplicated(keep="first")]
    act.loc[j.index, "zone_district"] = j["ZONE_DISTRICT"].values
    act.loc[j.index, "zone_use_form"] = j["ZONE_USE_FORM"].values
    act.loc[j.index, "single_unit_zoning"] = (j["ZONE_USE_FORM"] == "SU").values
    stats["permits_matched_zoning"] = int(j["ZONE_DISTRICT"].notna().sum())

    # growth area join
    j2 = gpd.sjoin(act_p, bp[["GROWTH_FUTURE", "PLCTYPE_FUT", "geometry"]], how="left", predicate="within")
    j2 = j2[~j2.index.duplicated(keep="first")]
    matched = j2["GROWTH_FUTURE"].notna()
    act.loc[j2.index[matched], "in_growth_area"] = True
    act.loc[j2.index[matched], "growth_future"] = j2.loc[j2.index[matched], "GROWTH_FUTURE"].values
    act.loc[j2.index[matched], "plctype_fut"] = j2.loc[j2.index[matched], "PLCTYPE_FUT"].values

    # transit: distance to nearest station
    from shapely.ops import nearest_points  # noqa
    station_geoms = stations.geometry.tolist()
    # vectorized-ish: use sjoin with buffered stations
    buf = stations.copy()
    buf["geometry"] = buf.geometry.buffer(M)
    j3 = gpd.sjoin(act_p, buf[["geometry"]], how="left", predicate="within")
    near_idx = j3[j3["index_right"].notna()].index.unique()
    act.loc[near_idx, "near_transit_halfmi"] = True

    # neighborhoods
    j4 = gpd.sjoin(act_p, nbhd[["NBHD_NAME", "geometry"]], how="left", predicate="within")
    j4 = j4[~j4.index.duplicated(keep="first")]
    act.loc[j4.index, "nbhd_spatial"] = j4["NBHD_NAME"].values
    agree = (act["nbhd_spatial"] == act["NEIGHBORHOOD"]).sum()
    print(f"neighborhood field vs spatial agreement: {agree}/{len(act)}")

    # ---- headline stats ----
    nb = act[act["cls"] == "new_building"]
    stats["new_building_total"] = len(nb)
    stats["new_building_in_su_zoning"] = int(nb["single_unit_zoning"].sum())
    stats["new_building_in_growth_area"] = int(nb["in_growth_area"].sum())
    stats["new_building_near_transit"] = int(nb["near_transit_halfmi"].sum())
    stats["all_permits_near_transit"] = int(act["near_transit_halfmi"].sum())

    # where are new buildings going, by growth type
    gt = nb[nb["in_growth_area"]]["growth_future"].value_counts()
    stats["new_building_by_growth_type"] = {k: int(v) for k, v in gt.items()}

    # zoning of new buildings
    zc = nb["single_unit_zoning"].value_counts()
    stats["new_building_zoning_split"] = {"single_unit_only": int(zc.get(True, 0)), "other": int(zc.get(False, 0))}

    # neighborhood aggregates
    agg = (
        act.groupby("nbhd_spatial")
        .agg(
            total_permits=("cls", "size"),
            new_buildings=("cls", lambda s: (s == "new_building").sum()),
            alterations=("cls", lambda s: (s == "alteration").sum()),
            adu=("is_adu", "sum"),
            in_growth=("in_growth_area", "sum"),
            near_transit=("near_transit_halfmi", "sum"),
            su_zoned=("single_unit_zoning", "sum"),
        )
        .reset_index()
        .rename(columns={"nbhd_spatial": "neighborhood"})
    )
    agg.to_csv(f"{OUT}/neighborhood_aggregates.csv", index=False)
    top = agg.sort_values("new_buildings", ascending=False)
    stats["top5_neighborhoods_new_buildings"] = [
        {"neighborhood": r["neighborhood"], "new_buildings": int(r["new_buildings"]), "total_permits": int(r["total_permits"])}
        for _, r in top.head(5).iterrows()
    ]
    stats["bottom10_neighborhoods_new_buildings"] = [
        {"neighborhood": r["neighborhood"], "new_buildings": int(r["new_buildings"]), "total_permits": int(r["total_permits"])}
        for _, r in top.tail(10).iterrows()
    ]
    stats["neighborhoods_zero_new_buildings"] = int((agg["new_buildings"] == 0).sum())

    with open(f"{OUT}/stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    print(json.dumps(stats, indent=2))

    # ---- enriched feature-layer outputs ----
    keep = [
        "PERMIT_NUM", "ADDRESS", "NEIGHBORHOOD", "date", "cls", "is_adu",
        "VALUATION", "UNITS", "zone_district", "zone_use_form", "single_unit_zoning",
        "in_growth_area", "growth_future", "plctype_fut", "near_transit_halfmi",
        "nbhd_spatial", "geometry",
    ]
    enr = act[keep].copy()
    enr["date"] = enr["date"].dt.strftime("%Y-%m-%d")
    enr.to_crs("EPSG:4326").to_file(f"{OUT}/permits_enriched.geojson", driver="GeoJSON")
    print("wrote permits_enriched.geojson:", len(enr))

    nm = nbhd.merge(agg, left_on="NBHD_NAME", right_on="neighborhood", how="left").fillna(0)
    nm.to_crs("EPSG:4326").to_file(f"{OUT}/neighborhoods_summary.geojson", driver="GeoJSON")
    print("wrote neighborhoods_summary.geojson:", len(nm))

    make_charts(monthly, nc, agg, stats)
    print("done")


def make_charts(monthly, nc, agg, stats):
    plt.rcParams.update({"font.size": 11})
    # 1. monthly new construction with rate-shock annotation
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(nc.index, nc.values, color="#1f6feb", lw=2)
    ax.fill_between(nc.index, nc.values, alpha=0.15, color="#1f6feb")
    ax.axvline(pd.Timestamp("2022-03-01"), color="#d97706", ls="--", lw=1.5)
    ax.text(pd.Timestamp("2022-03-15"), nc.max() * 0.95, "Fed hikes begin\nMar 2022", color="#d97706", fontsize=9)
    ax.axvline(pd.Timestamp("2022-10-01"), color="#dc2626", ls="--", lw=1.5)
    ax.text(pd.Timestamp("2022-10-15"), nc.max() * 0.80, "30-yr mortgage >7%\nOct 2022", color="#dc2626", fontsize=9)
    ax.set_title("Denver new residential construction permits per month, 2020-2026")
    ax.set_ylabel("permits issued")
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.tight_layout()
    fig.savefig(f"{CH}/monthly_new_construction.png", dpi=150)
    plt.close(fig)

    # 2. stacked monthly by class
    order = ["new_building", "phased", "site_prep", "addition", "alteration"]
    labels = {"new_building": "New building", "phased": "Phased construction", "site_prep": "Foundation/excavation",
              "addition": "Addition", "alteration": "Alteration/repair"}
    cols = ["#1f6feb", "#7c3aed", "#06b6d4", "#f59e0b", "#9ca3af"]
    fig, ax = plt.subplots(figsize=(11, 5))
    bottom = None
    for c, col in zip(order, cols):
        vals = monthly[c] if c in monthly else 0
        ax.bar(monthly.index, vals, width=28, bottom=bottom, label=labels[c], color=col)
        bottom = vals if bottom is None else bottom + vals
    ax.set_title("Denver residential permits per month by type, 2020-2026")
    ax.set_ylabel("permits issued")
    ax.legend(fontsize=9, ncol=3)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.tight_layout()
    fig.savefig(f"{CH}/monthly_by_class.png", dpi=150)
    plt.close(fig)

    # 3. new buildings: zoning split
    fig, ax = plt.subplots(figsize=(7, 5))
    vals = [stats["new_building_zoning_split"]["single_unit_only"], stats["new_building_zoning_split"]["other"]]
    ax.bar(["Single-unit-only\nzoning", "All other\nzoning"], vals, color=["#d97706", "#1f6feb"])
    for i, v in enumerate(vals):
        ax.text(i, v + max(vals) * 0.02, f"{v:,}", ha="center", fontsize=12, fontweight="bold")
    ax.set_title("New-building permits by zoning, 2020-2026")
    ax.set_ylabel("permits")
    fig.tight_layout()
    fig.savefig(f"{CH}/zoning_split.png", dpi=150)
    plt.close(fig)

    # 4. growth areas
    fig, ax = plt.subplots(figsize=(7, 5))
    vals = [stats["new_building_in_growth_area"], stats["new_building_total"] - stats["new_building_in_growth_area"]]
    ax.bar(["Inside Blueprint\ngrowth areas", "Everywhere else"], vals, color=["#059669", "#9ca3af"])
    for i, v in enumerate(vals):
        ax.text(i, v + max(vals) * 0.02, f"{v:,}", ha="center", fontsize=12, fontweight="bold")
    ax.set_title("New-building permits: Blueprint Denver growth areas, 2020-2026")
    ax.set_ylabel("permits")
    fig.tight_layout()
    fig.savefig(f"{CH}/growth_areas.png", dpi=150)
    plt.close(fig)

    # 5. transit
    fig, ax = plt.subplots(figsize=(7, 5))
    vals = [stats["new_building_near_transit"], stats["new_building_total"] - stats["new_building_near_transit"]]
    ax.bar(["Within 1/2 mi of\nrail station", "Farther than 1/2 mi"], vals, color=["#7c3aed", "#9ca3af"])
    for i, v in enumerate(vals):
        ax.text(i, v + max(vals) * 0.02, f"{v:,}", ha="center", fontsize=12, fontweight="bold")
    ax.set_title("New-building permits near RTD rail, 2020-2026")
    ax.set_ylabel("permits")
    fig.tight_layout()
    fig.savefig(f"{CH}/transit.png", dpi=150)
    plt.close(fig)

    # 6. top/bottom neighborhoods
    top = agg.sort_values("new_buildings", ascending=False)
    fig, axes = plt.subplots(1, 2, figsize=(13, 6), sharex=False)
    t15 = top.head(15).iloc[::-1]
    axes[0].barh(t15["neighborhood"], t15["new_buildings"], color="#1f6feb")
    axes[0].set_title("Most new-building permits")
    b15 = top.tail(15)
    axes[1].barh(b15["neighborhood"], b15["new_buildings"], color="#d97706")
    axes[1].set_title("Fewest new-building permits")
    for axi in axes:
        axi.tick_params(labelsize=9)
    fig.suptitle("New-building permits by Denver neighborhood, 2020-2026")
    fig.tight_layout()
    fig.savefig(f"{CH}/neighborhoods.png", dpi=150)
    plt.close(fig)

    # 7. choropleth
    nbhd = gpd.read_file(f"{DATA}/neighborhoods.geojson")
    m = nbhd.merge(agg, left_on="NBHD_NAME", right_on="neighborhood", how="left")
    fig, ax = plt.subplots(figsize=(10, 9))
    m.plot(column="new_buildings", ax=ax, legend=True, cmap="YlOrRd", edgecolor="white", linewidth=0.4,
           legend_kwds={"label": "New-building permits, 2020-2026"}, missing_kwds={"color": "#e5e7eb"})
    ax.set_title("Where Denver builds: new-building permits by neighborhood, 2020-2026")
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(f"{CH}/map_new_buildings.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
