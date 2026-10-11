"""Download Denver permit/zoning/plan/neighborhood layers from ArcGIS Hub.

Sources (all City and County of Denver, ArcGIS Hub org zdB7qR0BtYrg0Xpl):
- ODC_DEV_RESIDENTIALCONSTPERMIT_P/316  DEV_RESIDENTIALCONSTPERMIT_P (permits)
- ODC_ZONE_ZONING_A/209                 ZONE_ZONING_A (zoning polygons)
- ODC_PLAN_BPFUTUREPLACES_A/101         PLAN_BPFUTUREPLACES_A (Blueprint Denver future places)
- ODC_ADMN_NEIGHBORHOOD_A/13            ADMN_NEIGHBORHOOD_A (statistical neighborhoods)
RTD rail stations come from RTD's public GTFS feed (see code/rtd_stations.py).
"""
import json
import time
import urllib.parse
import urllib.request

BASE = "https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services"
DATA = "/home/hatch/workspace/denver-housing-permits/data"


def fetch_paged(url, where, out_fields, page_size=2000, max_pages=1000):
    feats = []
    offset = 0
    for _ in range(max_pages):
        q = {
            "where": where,
            "outFields": out_fields,
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": page_size,
        }
        req_url = url + "/query?" + urllib.parse.urlencode(q)
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req_url, timeout=120) as r:
                    page = json.load(r)
                break
            except Exception as e:
                if attempt == 3:
                    raise
                time.sleep(2 * (attempt + 1))
        batch = page.get("features", [])
        feats.extend(batch)
        print(f"  offset {offset}: +{len(batch)} (total {len(feats)})", flush=True)
        if len(batch) < page_size or page.get("exceededTransferLimit") is False and len(batch) == 0:
            break
        if not page.get("exceededTransferLimit", True) and len(batch) < page_size:
            break
        offset += page_size
        if len(batch) < page_size:
            break
    return {"type": "FeatureCollection", "features": feats}


def save(name, fc):
    path = f"{DATA}/{name}.geojson"
    with open(path, "w") as f:
        json.dump(fc, f)
    print(f"saved {path}: {len(fc['features'])} features")


def main():
    print("permits 2020+ ...")
    fc = fetch_paged(
        f"{BASE}/ODC_DEV_RESIDENTIALCONSTPERMIT_P/FeatureServer/316",
        "DATE_ISSUED >= TIMESTAMP '2020-01-01 00:00:00'",
        "OBJECTID,DATE_ISSUED,PERMIT_NUM,ADDRESS,CLASS,UNITS,VALUATION,PERMIT_FEE,"
        "FINAL_DATE,CANCEL,DATE_RECEIVED,NEIGHBORHOOD,STAT_CODE_1,STAT_CODE_2,STAT_CODE_3",
    )
    save("permits_2020", fc)

    print("zoning ...")
    fc = fetch_paged(
        f"{BASE}/ODC_ZONE_ZONING_A/FeatureServer/209",
        "1=1",
        "OBJECTID,ZONE_DISTRICT,ZONE_DISTRICT_GROUP,ZONE_USE_FORM,NBHD_CONTEXT,"
        "ZONE_DIST_TYPE,OVERLAY_DISTRICT,ADU",
    )
    save("zoning", fc)

    print("blueprint future places (growth areas only) ...")
    fc = fetch_paged(
        f"{BASE}/ODC_PLAN_BPFUTUREPLACES_A/FeatureServer/101",
        "GROWTH_FUTURE <> 'All other areas of the city'",
        "OBJECTID,PLCTYPE_FUT,GROWTH_FUTURE,FUT_NBHD_CONTEXT",
    )
    save("bp_growth_areas", fc)

    print("neighborhoods ...")
    fc = fetch_paged(
        f"{BASE}/ODC_ADMN_NEIGHBORHOOD_A/FeatureServer/13",
        "1=1",
        "OBJECTID,NBHD_ID,NBHD_NAME,TYPOLOGY",
    )
    save("neighborhoods", fc)


if __name__ == "__main__":
    main()
