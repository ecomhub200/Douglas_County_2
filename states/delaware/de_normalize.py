#!/usr/bin/env python3
"""
de_normalize.py — CrashLens Delaware (DelDOT) — Full 8-Phase Pipeline
State: Delaware | FIPS: 10 | DOT: DelDOT

AUTO-IMPORTS all shared modules from repo root:
  geo_resolver.py      → Phase 3 (FIPS, Place FIPS, Ownership, Area Type)
  crash_enricher.py    → Phase 8 (flags from circumstance + OSM road matching)
  osm_road_enricher.py → Auto-downloads OSM data if cache missing (called by Phase 8)

SMART ENRICHMENT: Only fills EMPTY columns. If a state already has data
(e.g., Virginia has Functional Class), that column is SKIPPED, not overwritten.

Pipeline (8 phases):
  Phase 1 — Column Mapping & Rename
  Phase 2 — State-Specific Value Transforms
  Phase 3 — FIPS Resolution (hardcoded + geo_resolver)
  Phase 4 — Composite Crash ID Generation
  Phase 5 — EPDO Scoring
  Phase 6 — Jurisdiction Ranking (24 columns)
  Phase 7 — Validation & Reporting
  Phase 8 — Universal Enrichment (auto-downloads OSM if needed)

Usage:
    python de_normalize.py --input raw_crashes.csv
    python de_normalize.py --input raw_crashes.csv --output normalized.csv
    python de_normalize.py --input raw_crashes.csv --epdo vdot2024
    python de_normalize.py --input raw_crashes.csv --skip-enrichment
"""

import argparse, json, os, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
#  PATH RESOLUTION — auto-discover repo root and all shared modules
#  This script: states/delaware/de_normalize.py
#  Repo root:   ../../
# ─────────────────────────────────────────────────────────────────────────────

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT  = _SCRIPT_DIR.parent.parent
_GEO_DIR    = _SCRIPT_DIR.parent / "geography"
_HIER_PATH  = _SCRIPT_DIR / "hierarchy.json"
_CACHE_DIR  = _REPO_ROOT / "cache"

# Flat folder fallback: if hierarchy.json is next to script, use it
if not _HIER_PATH.exists() and (_SCRIPT_DIR / "hierarchy.json").exists():
    _HIER_PATH = _SCRIPT_DIR / "hierarchy.json"
# Flat folder fallback: if cache/ is next to script
if not _CACHE_DIR.exists() and (_SCRIPT_DIR / "cache").exists():
    _CACHE_DIR = _SCRIPT_DIR / "cache"
if not _CACHE_DIR.exists():
    _CACHE_DIR = _SCRIPT_DIR / "cache"  # will be auto-created

# Add repo root to sys.path — this is how ALL shared modules are found
# Also add script dir as fallback (for flat folder layout when all files are together)
for p in [str(_REPO_ROOT), str(_SCRIPT_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# ─────────────────────────────────────────────────────────────────────────────
#  STATE CONFIG
# ─────────────────────────────────────────────────────────────────────────────

STATE_FIPS = "10"; STATE_ABBR = "DE"; STATE_NAME = "Delaware"; STATE_DOT = "DelDOT"

# The contributing circumstance column name in Delaware's source data
# (crash_enricher uses this to derive Distracted?, Speed?, etc.)
CIRCUMSTANCE_COL = "PRIMARY CONTRIBUTING CIRCUMSTANCE DESCRIPTION"
PRIVATE_PROPERTY_COL = "COLLISION ON PRIVATE PROPERTY"

GOLDEN_COLUMNS = [
    "OBJECTID","Document Nbr","Crash Year","Crash Date","Crash Military Time",
    "Crash Severity","K_People","A_People","B_People","C_People",
    "Persons Injured","Pedestrians Killed","Pedestrians Injured","Vehicle Count",
    "Collision Type","Weather Condition","Light Condition","Roadway Surface Condition",
    "Relation To Roadway","Roadway Alignment","Roadway Surface Type","Roadway Defect",
    "Roadway Description","Intersection Type","Traffic Control Type","Traffic Control Status",
    "Work Zone Related","Work Zone Location","Work Zone Type","School Zone",
    "First Harmful Event","First Harmful Event Loc",
    "Alcohol?","Animal Related?","Unrestrained?","Bike?","Distracted?","Drowsy?",
    "Drug Related?","Guardrail Related?","Hitrun?","Lgtruck?","Motorcycle?","Pedestrian?",
    "Speed?","Max Speed Diff","RoadDeparture Type","Intersection Analysis",
    "Senior?","Young?","Mainline?","Night?",
    "VDOT District","Juris Code","Physical Juris Name","Functional Class",
    "Facility Type","Area Type","SYSTEM","VSP","Ownership",
    "Planning District","MPO Name","RTE Name","RNS MP","Node","Node Offset (ft)","x","y",
]
ENRICHMENT_COLUMNS = ["FIPS","Place FIPS","EPDO_Score"]
RANKING_SCOPES = ["District","Juris","PlanningDistrict","MPO"]
RANKING_METRICS = ["total_crash","total_ped_crash","total_bike_crash","total_fatal","total_fatal_serious_injury","total_epdo"]
EPDO_PRESETS = {
    "hsm2010":{"K":462,"A":62,"B":12,"C":5,"O":1},
    "vdot2024":{"K":1032,"A":53,"B":16,"C":10,"O":1},
    "fhwa2022":{"K":975,"A":48,"B":13,"C":8,"O":1},
    "fhwa2025":{"K":883,"A":94,"B":21,"C":11,"O":1},
}
DEFAULT_EPDO_PRESET = "fhwa2025"

# ─────────────────────────────────────────────────────────────────────────────
#  DELAWARE GEOGRAPHY + VALUE MAPS  (state-specific — edit per state)
# ─────────────────────────────────────────────────────────────────────────────

DE_COUNTIES = {
    "Kent":{"fips":"001","geoid":"10001","district":"Central District","mpo":"Dover/Kent County MPO"},
    "New Castle":{"fips":"003","geoid":"10003","district":"North District","mpo":"WILMAPCO"},
    "Sussex":{"fips":"005","geoid":"10005","district":"South District","mpo":"Salisbury-Wicomico MPO"},
}
DE_COUNTY_CODE_MAP = {"K":"Kent","N":"New Castle","S":"Sussex"}
AREA_TYPE_MAP = {"Kent":"Rural","New Castle":"Urban","Sussex":"Rural"}

MAP_SEVERITY = {"fatality crash":"K","fatal crash":"K","fatal":"K","personal injury crash":"A","injury crash":"A","personal injury":"A","property damage only":"O","property damage":"O","pdo":"O","non-reportable":"O","non reportable":"O"}
MAP_COLLISION_TYPE = {"front to rear":"1. Rear End","angle":"2. Angle","front to front":"3. Head On","sideswipe, same direction":"4. Sideswipe - Same Direction","sideswipe, opposite direction":"5. Sideswipe - Opposite Direction","not a collision between two vehicles":"8. Non-Collision","rear to rear":"16. Other","rear to side":"16. Other","other":"16. Other","unknown":"Not Provided"}
MAP_WEATHER = {"clear":"1. No Adverse Condition (Clear/Cloudy)","cloudy":"1. No Adverse Condition (Clear/Cloudy)","fog, smog, smoke":"3. Fog","rain":"5. Rain","snow":"6. Snow","sleet, hail (freezing rain or drizzle)":"7. Sleet/Hail","blowing sand, soil, dirt":"10. Blowing Sand, Soil, Dirt, or Snow","blowing snow":"10. Blowing Sand, Soil, Dirt, or Snow","severe crosswinds":"11. Severe Crosswinds","other":"9. Other","unknown":"Not Applicable"}
MAP_LIGHT = {"dawn":"1. Dawn","daylight":"2. Daylight","dusk":"3. Dusk","dark-lighted":"4. Darkness - Road Lighted","dark-not lighted":"5. Darkness - Road Not Lighted","dark-unknown lighting":"6. Darkness - Unknown Road Lighting","other":"7. Unknown","unknown":"7. Unknown"}
MAP_ROAD_SURFACE = {"dry":"1. Dry","wet":"2. Wet","snow":"3. Snow/Ice","ice/frost":"3. Snow/Ice","slush":"4. Slush","mud, dirt, gravel":"5. Sand/Mud/Dirt/Oil/Gravel","sand":"5. Sand/Mud/Dirt/Oil/Gravel","oil":"5. Sand/Mud/Dirt/Oil/Gravel","water (standing, moving)":"6. Water (Standing/Moving)","other":"9. Other","unknown":"Not Applicable"}
MAP_WORK_ZONE_LOCATION = {"advance warning area":"1. Advance Warning Area","before the first work zone warning sign":"1. Advance Warning Area","transition area":"2. Transition Area","activity area":"3. Activity Area","termination area":"4. Termination Area"}
MAP_WORK_ZONE_TYPE = {"lane closure":"1. Lane Closure","lane shift/crossover":"2. Lane Shift/Crossover","work on shoulder or median":"3. Work on Shoulder or Median","intermittent or moving work":"4. Intermittent or Moving Work","other":"5. Other"}
MAP_SCHOOL_BUS_TO_ZONE = {"no":"3. No","yes, directly involved":"2. Yes - With School Activity","yes, indirectly involved":"1. Yes"}

COLUMN_RENAMES = {
    "CRASH DATETIME":"Crash Date","YEAR":"Crash Year","LATITUDE":"y","LONGITUDE":"x",
    "COUNTY NAME":"Physical Juris Name","COUNTY CODE":"Juris Code",
    "PEDESTRIAN INVOLVED":"Pedestrian?","BICYCLED INVOLVED":"Bike?",
    "ALCOHOL INVOLVED":"Alcohol?","DRUG INVOLVED":"Drug Related?",
    "MOTORCYCLE INVOLVED":"Motorcycle?","SEATBELT USED":"Unrestrained?",
    "WEATHER 1 DESCRIPTION":"Weather Condition","LIGHTING CONDITION DESCRIPTION":"Light Condition",
    "ROAD SURFACE DESCRIPTION":"Roadway Surface Condition","MANNER OF IMPACT DESCRIPTION":"Collision Type",
    "SCHOOL BUS INVOLVED DESCRIPTION":"School Zone","WORK ZONE":"Work Zone Related",
    "WORK ZONE LOCATION DESCRIPTION":"Work Zone Location","WORK ZONE TYPE DESCRIPTION":"Work Zone Type",
    "CRASH CLASSIFICATION DESCRIPTION":"Crash Severity",
}
EXTRA_COLUMNS = [
    "DAY OF WEEK CODE","DAY OF WEEK DESCRIPTION","CRASH CLASSIFICATION CODE",
    "COLLISION ON PRIVATE PROPERTY","MANNER OF IMPACT CODE","ROAD SURFACE CODE",
    "LIGHTING CONDITION CODE","WEATHER 1 CODE","WEATHER 2 CODE","WEATHER 2 DESCRIPTION",
    "MOTORCYCLE HELMET USED","BICYCLE HELMET USED","SCHOOL BUS INVOLVED CODE",
    "WORK ZONE LOCATION CODE","WORK ZONE TYPE CODE","WORKERS PRESENT",
    "PRIMARY CONTRIBUTING CIRCUMSTANCE CODE","PRIMARY CONTRIBUTING CIRCUMSTANCE DESCRIPTION",
]

# ─────────────────────────────────────────────────────────────────────────────
#  DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def is_already_normalized(columns):
    return {"Document Nbr","Crash Severity","Physical Juris Name","x","y"}.issubset(set(columns))

# ─────────────────────────────────────────────────────────────────────────────
#  PHASE 1: COLUMN RENAMES
# ─────────────────────────────────────────────────────────────────────────────

def apply_column_renames(df):
    src = {c.strip().upper(): c for c in df.columns}
    rmap = {src[s]: t for s, t in COLUMN_RENAMES.items() if s in src}
    df = df.rename(columns=rmap)
    for col in GOLDEN_COLUMNS:
        if col not in df.columns: df[col] = ""
    return df

# ─────────────────────────────────────────────────────────────────────────────
#  PHASE 2: VALUE TRANSFORMS
# ─────────────────────────────────────────────────────────────────────────────

_MONTHS = {"jan":"01","feb":"02","mar":"03","apr":"04","may":"05","jun":"06","jul":"07","aug":"08","sep":"09","oct":"10","nov":"11","dec":"12"}

def parse_delaware_datetime(raw):
    if not raw or not raw.strip(): return "","",""
    p = raw.strip().split()
    if len(p) < 4: return raw,"",""
    yr=p[0]; mn=_MONTHS.get(p[1].lower(),"01"); dy=p[2]
    tp=p[3].split(":"); h=int(tp[0]) if tp else 0; mi=tp[1] if len(tp)>1 else "00"
    ap=p[4].upper() if len(p)>4 else ""
    if ap=="PM" and h<12: h+=12
    elif ap=="AM" and h==12: h=0
    return f"{int(mn)}/{int(dy)}/{yr}", f"{h:02d}{mi}", yr

def apply_value_transforms(df):
    # Datetime
    if "Crash Date" in df.columns:
        parsed = df["Crash Date"].fillna("").apply(parse_delaware_datetime)
        df["Crash Date"] = parsed.apply(lambda t:t[0])
        df["Crash Military Time"] = parsed.apply(lambda t:t[1])
        yr = parsed.apply(lambda t:t[2])
        m = df["Crash Year"].fillna("").str.strip()==""
        df.loc[m,"Crash Year"] = yr[m]

    # Value maps (vectorized)
    _map = lambda col,d,fb: df.__setitem__(col, df[col].fillna("").str.strip().str.lower().map(d).fillna(fb)) if col in df.columns else None
    _map("Crash Severity", MAP_SEVERITY, "O")
    _map("Collision Type", MAP_COLLISION_TYPE, "Not Provided")
    _map("Weather Condition", MAP_WEATHER, "Not Applicable")
    _map("Light Condition", MAP_LIGHT, "7. Unknown")
    _map("Roadway Surface Condition", MAP_ROAD_SURFACE, "Not Applicable")
    _map("Work Zone Location", MAP_WORK_ZONE_LOCATION, "")
    _map("Work Zone Type", MAP_WORK_ZONE_TYPE, "")
    _map("School Zone", MAP_SCHOOL_BUS_TO_ZONE, "3. No")

    # Y/N booleans
    yn = {"Y":"Yes","N":"No","YES":"Yes","NO":"No"}
    for c in ["Pedestrian?","Alcohol?","Drug Related?","Motorcycle?","Bike?"]:
        if c in df.columns: df[c] = df[c].fillna("").str.strip().str.upper().map(yn).fillna("No")

    # Unrestrained (inverted seatbelt)
    if "Unrestrained?" in df.columns:
        df["Unrestrained?"] = df["Unrestrained?"].fillna("").str.strip().str.upper().map({"Y":"Belted","N":"Unbelted","YES":"Belted","NO":"Unbelted"}).fillna("Belted")

    # Work Zone Related → "1. Yes" / "2. No"
    if "Work Zone Related" in df.columns:
        df["Work Zone Related"] = df["Work Zone Related"].fillna("").str.strip().str.upper().map({"Y":"1. Yes","N":"2. No","YES":"1. Yes","NO":"2. No"}).fillna("2. No")

    # Night? from ALREADY-MAPPED Light Condition
    if "Light Condition" in df.columns:
        df["Night?"] = df["Light Condition"].isin({"1. Dawn","3. Dusk","4. Darkness - Road Lighted","5. Darkness - Road Not Lighted","6. Darkness - Unknown Road Lighting"}).map({True:"Yes",False:"No"})

    # Area Type
    if "Physical Juris Name" in df.columns:
        df["Area Type"] = df["Physical Juris Name"].map(AREA_TYPE_MAP).fillna("Rural")

    return df

# ─────────────────────────────────────────────────────────────────────────────
#  PHASE 3: FIPS (hardcoded + geo_resolver)
# ─────────────────────────────────────────────────────────────────────────────

def resolve_fips(df):
    fips_lookup = {c: {"fips":g["fips"],"countyName":c,"geoid":g["geoid"],"region":g["district"],"mpo":g["mpo"],"source":"state_transform"} for c,g in DE_COUNTIES.items()}

    def _assign(row):
        j = str(row.get("Physical Juris Name","")).strip()
        if j in DE_COUNTY_CODE_MAP: j = DE_COUNTY_CODE_MAP[j]
        g = DE_COUNTIES.get(j, {})
        row["FIPS"]=g.get("fips",""); row["Place FIPS"]=""
        row["VDOT District"]=g.get("district",""); row["Planning District"]=g.get("district","")
        row["MPO Name"]=g.get("mpo","")
        if j in DE_COUNTIES: row["Physical Juris Name"]=j
        return row
    df = df.apply(_assign, axis=1)

    try:
        from geo_resolver import GeoResolver
        if _GEO_DIR.is_dir():
            hp = str(_HIER_PATH) if _HIER_PATH.exists() else None
            resolver = GeoResolver(STATE_FIPS, STATE_ABBR, str(_GEO_DIR), hp)
            rows = df.to_dict('records'); resolver.resolve_all(rows); df = pd.DataFrame(rows)
            print("        geo_resolver: enhanced geography")
    except ImportError: print("        geo_resolver not found — hardcoded only")
    except Exception as e: print(f"        geo_resolver error: {e}")
    return df, fips_lookup

# ─────────────────────────────────────────────────────────────────────────────
#  PHASE 4: CRASH IDs  |  PHASE 5: EPDO  |  PHASE 6: RANKINGS
# ─────────────────────────────────────────────────────────────────────────────

def generate_crash_ids(df):
    needs = df["Document Nbr"].fillna("").str.strip()==""
    def _mk(i, row):
        d=str(row["Crash Date"]); p=d.split("/")
        dc = f"{p[2]}{int(p[0]):02d}{int(p[1]):02d}" if len(p)==3 else re.sub(r"[^0-9]","",d)[:8].ljust(8,"0")
        t = str(row.get("Crash Military Time","0000") or "0000").strip().ljust(4,"0")
        return f"DE-{dc}-{t}-{i+1:07d}"
    ids = [_mk(i,row) if needs.iloc[i] else df["Document Nbr"].iloc[i] for i,(_,row) in enumerate(df.iterrows())]
    df["Document Nbr"]=ids; df["OBJECTID"]=[str(i+1) for i in range(len(df))]
    return df

def compute_epdo(df, weights):
    df["EPDO_Score"] = df["Crash Severity"].map({s:weights[s] for s in "KABCO"}).fillna(weights["O"]).astype(int)
    return df

def compute_rankings(df):
    metrics = {}
    for _, row in df.iterrows():
        k = str(row.get("FIPS","")).strip() or str(row.get("Physical Juris Name","")).strip()
        if not k: continue
        if k not in metrics:
            metrics[k] = {"juris":str(row.get("Physical Juris Name","")),"district":str(row.get("VDOT District","") or ""),"mpo":str(row.get("MPO Name","") or ""),"pd":str(row.get("Planning District","") or ""),"total_crash":0,"total_ped_crash":0,"total_bike_crash":0,"total_fatal":0,"total_fatal_serious_injury":0,"total_epdo":0}
        m=metrics[k]; m["total_crash"]+=1; m["total_epdo"]+=int(row.get("EPDO_Score",1) or 1)
        if str(row.get("Pedestrian?",""))=="Yes": m["total_ped_crash"]+=1
        if str(row.get("Bike?",""))=="Yes": m["total_bike_crash"]+=1
        s=str(row.get("Crash Severity",""))
        if s=="K": m["total_fatal"]+=1
        if s in ("K","A"): m["total_fatal_serious_injury"]+=1

    def _rk(groups, metric):
        rm={}
        for entries in groups.values():
            se=sorted(entries,key=lambda x:x[1][metric],reverse=True); r=0; pv=-1
            for i,(k,m) in enumerate(se):
                if m[metric]!=pv: r=i+1; pv=m[metric]
                rm[k]=r
        return rm

    rr={k:{} for k in metrics}
    for metric in RANKING_METRICS:
        rm=_rk({"ALL":list(metrics.items())},metric)
        for k,r in rm.items(): rr[k][f"Juris_Rank_{metric}"]=r
        for scope,gk in [("District","district"),("MPO","mpo"),("PlanningDistrict","pd")]:
            groups={}
            for k,m in metrics.items():
                g=m[gk] or ""
                if g: groups.setdefault(g,[]).append((k,m))
                else: rr[k][f"{scope}_Rank_{metric}"]=None
            rm=_rk(groups,metric)
            for k,r in rm.items(): rr[k][f"{scope}_Rank_{metric}"]=r

    for s in RANKING_SCOPES:
        for m in RANKING_METRICS: df[f"{s}_Rank_{m}"]=""
    def _apply(row):
        k=str(row.get("FIPS","")).strip() or str(row.get("Physical Juris Name","")).strip()
        ranks=rr.get(k,{})
        for s in RANKING_SCOPES:
            for m in RANKING_METRICS:
                c=f"{s}_Rank_{m}"; v=ranks.get(c); row[c]="" if v is None else str(v)
        return row
    df=df.apply(_apply,axis=1)
    return df, metrics

# ─────────────────────────────────────────────────────────────────────────────
#  PHASE 8: ENRICHMENT (auto-imports + auto-downloads OSM if needed)
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_osm_cache():
    """Auto-download OSM road network if cache doesn't exist."""
    cache_file = _CACHE_DIR / f"{STATE_ABBR.lower()}_roads.parquet"
    if cache_file.exists():
        return True

    print(f"        OSM cache not found — attempting auto-download for {STATE_NAME}...")
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Strategy 1: Import from osm_road_enricher.py (shared module)
    try:
        import osm_road_enricher
        # Try known function signatures
        if hasattr(osm_road_enricher, 'download_state_roads'):
            osm_road_enricher.download_state_roads(STATE_NAME, STATE_ABBR, str(_CACHE_DIR))
        elif hasattr(osm_road_enricher, 'download'):
            osm_road_enricher.download(STATE_NAME, STATE_ABBR, str(_CACHE_DIR))
        else:
            # Run as CLI subprocess fallback
            import subprocess
            subprocess.run([sys.executable, str(_REPO_ROOT / "osm_road_enricher.py"),
                           "download", "--state", STATE_ABBR], check=True)
        return cache_file.exists()
    except ImportError:
        print("        osm_road_enricher.py not found — Tier 2 skipped")
        print("        (Place osm_road_enricher.py next to this script or at repo root)")
        return False
    except Exception as e:
        print(f"        OSM auto-download failed: {e}")
        print("        Tier 2 skipped — Tier 1 (flag derivation) still runs")
        return False

def run_enrichment(df, skip_enrichment=False):
    """Import crash_enricher and run. Smart: only fills EMPTY columns."""
    if skip_enrichment:
        print("        Skipped (--skip-enrichment)")
        return df
    try:
        from crash_enricher import CrashEnricher
        osm_ready = _ensure_osm_cache()
        enricher = CrashEnricher(
            state_fips=STATE_FIPS, state_abbr=STATE_ABBR, state_name=STATE_NAME,
            cache_dir=str(_CACHE_DIR), circumstance_col=CIRCUMSTANCE_COL,
            private_property_col=PRIVATE_PROPERTY_COL,
        )
        df = enricher.enrich_all(df, skip_tier2=not osm_ready)
    except ImportError:
        print("        crash_enricher.py not found — enrichment skipped")
        print("        (Place crash_enricher.py in repo root for auto-enrichment)")
    except Exception as e:
        print(f"        Enrichment error: {e}")
    return df

# ─────────────────────────────────────────────────────────────────────────────
#  PHASE 7: VALIDATION REPORT
# ─────────────────────────────────────────────────────────────────────────────

def build_column_mapping_record(source_cols):
    su={c.upper().strip() for c in source_cols}; ru={k.upper():v for k,v in COLUMN_RENAMES.items()}; mp={}
    for t in GOLDEN_COLUMNS:
        if t in source_cols: mp[t]={"source":t,"status":"mapped"}
        elif t.upper() in ru.values():
            found=False
            for sk,tv in ru.items():
                if tv==t and sk in su: mp[t]={"source":sk,"status":"renamed"}; found=True; break
            if not found: mp[t]={"source":None,"status":"missing"}
        else: mp[t]={"source":None,"status":"missing"}
    return mp

def build_validation_report(df, fips_lookup, metrics, ep_name, ep_w, col_map):
    total=len(df); sd={s:int((df["Crash Severity"]==s).sum()) for s in "KABCO"}
    sd["unmapped"]=int((~df["Crash Severity"].isin(list("KABCO"))).sum())
    fr=sum(1 for v in fips_lookup.values() if v.get("fips"))
    mp=sum(1 for v in col_map.values() if v["status"]=="mapped")
    rn=sum(1 for v in col_map.values() if v["status"]=="renamed")
    mi=sum(1 for v in col_map.values() if v["status"]=="missing")
    q=round(0.5*(mp+rn)/len(GOLDEN_COLUMNS)*100+0.5*(fr/max(len(fips_lookup),1))*100,1)
    mc={}
    for c in ["Physical Juris Name","Functional Class","Ownership","Crash Severity","x","y"]:
        p=float((df[c].fillna("").str.strip()!="").sum())/max(total,1)*100
        mc[c]=f"OK ({p:.1f}% filled)" if p>90 else f"WARNING ({p:.1f}% filled)"
    return {"state":STATE_NAME,"state_fips":STATE_FIPS,"state_abbr":STATE_ABBR,
            "processed_at":datetime.now(timezone.utc).isoformat(),"total_rows":total,
            "total_columns":69+3+24,"quality_score":q,
            "fips_coverage":{"total":len(fips_lookup),"resolved":fr,"coverage_pct":round(fr/max(len(fips_lookup),1)*100,1)},
            "severity_distribution":sd,"epdo_config":{"preset":ep_name,"weights":ep_w},
            "mapping":{"mapped":mp,"renamed":rn,"missing":mi,"pct":round((mp+rn)/69*100,1)},
            "mandatory_columns":mc,"ranking_scopes":RANKING_SCOPES,"ranking_metrics":RANKING_METRICS,
            "warnings":[
                "DE does not distinguish B/C injuries — all injury → A",
                "Seatbelt inverted: Y(seatbelt)=Belted, not Unrestrained",
                "School Zone derived from School Bus Involved (approximate)",
                "Night? derived from already-mapped Light Condition values",
                "Work Zone Related uses '1. Yes'/'2. No' (numbered prefix)",
                "Functional Class filled by OSM enricher (Tier 2) when available",
                "Composite IDs generated: DE-YYYYMMDD-HHMM-NNNNNNN",
            ]}

# ─────────────────────────────────────────────────────────────────────────────
#  MAIN PIPELINE (8 phases, single command)
# ─────────────────────────────────────────────────────────────────────────────

def normalize(input_path, output_path=None, epdo_preset=DEFAULT_EPDO_PRESET,
              skip_if_normalized=False, report_path=None, skip_enrichment=False):
    t0=time.time(); src=Path(input_path)
    if not src.exists(): raise FileNotFoundError(f"Input not found: {src}")

    # Module status check
    has_geo = (_REPO_ROOT/"geo_resolver.py").exists()
    has_enrich = (_REPO_ROOT/"crash_enricher.py").exists()
    has_osm_dl = (_REPO_ROOT/"osm_road_enricher.py").exists()
    has_hier = _HIER_PATH.exists()
    has_cache = (_CACHE_DIR/f"{STATE_ABBR.lower()}_roads.parquet").exists()

    print(f"\n{'='*65}")
    print(f"  CrashLens {STATE_NAME} ({STATE_DOT}) | {datetime.now():%Y-%m-%d %H:%M}")
    print(f"  Input: {src.name}")
    print(f"  Shared modules at {_REPO_ROOT}:")
    print(f"    geo_resolver.py      {'OK' if has_geo else 'MISSING'}")
    print(f"    crash_enricher.py    {'OK' if has_enrich else 'MISSING'}")
    print(f"    osm_road_enricher.py {'OK' if has_osm_dl else 'MISSING (Tier 2 auto-download disabled)'}")
    print(f"    hierarchy.json       {'OK' if has_hier else 'MISSING (districts/MPO from hardcoded only)'}")
    print(f"    OSM road cache       {'CACHED' if has_cache else 'will auto-download on first run'}")
    print(f"{'='*65}")

    print("  [1/8] Loading CSV...")
    df=pd.read_csv(src,dtype=str,low_memory=False); df.columns=[c.strip() for c in df.columns]
    print(f"        {len(df):,} rows x {len(df.columns)} cols")
    if skip_if_normalized and is_already_normalized(df.columns.tolist()):
        print("  Already normalized — skipping"); return str(src)

    col_map=build_column_mapping_record(df.columns.tolist())

    print("  [2/8] Column renames..."); df=apply_column_renames(df)
    print("  [3/8] Value transforms..."); df=apply_value_transforms(df)
    print("  [4/8] FIPS resolution..."); df,fips=resolve_fips(df)
    print(f"        {sum(1 for v in fips.values() if v.get('fips'))}/{len(fips)} resolved")
    print("  [5/8] Crash IDs..."); df=generate_crash_ids(df)

    w=EPDO_PRESETS.get(epdo_preset,EPDO_PRESETS[DEFAULT_EPDO_PRESET])
    print(f"  [6/8] EPDO ({epdo_preset}) + Rankings...")
    df=compute_epdo(df,w); df,metrics=compute_rankings(df)
    print(f"        {len(metrics)} jurisdictions ranked")

    print("  [7/8] Validation report...")
    report=build_validation_report(df,fips,metrics,epdo_preset,w,col_map)

    print("  [8/8] Universal enrichment...")
    df=run_enrichment(df, skip_enrichment)

    # Output
    extra=[c for c in df.columns if c in EXTRA_COLUMNS]
    rcols=[f"{s}_Rank_{m}" for s in RANKING_SCOPES for m in RANKING_METRICS]
    out_cols=[c for c in GOLDEN_COLUMNS+ENRICHMENT_COLUMNS+rcols+extra if c in df.columns]
    if output_path is None: output_path=str(src.parent/f"{src.stem}_normalized_ranked.csv")
    if report_path is None: report_path=str(src.parent/f"{src.stem}_validation_report.json")
    df[out_cols].to_csv(output_path,index=False)
    with open(report_path,"w") as f: json.dump(report,f,indent=2)
    sev=report["severity_distribution"]
    print(f"\n  Done in {time.time()-t0:.1f}s | Quality: {report['quality_score']}% | K={sev['K']} A={sev['A']} O={sev['O']}")
    print(f"  Output: {output_path}")
    print(f"  Report: {report_path}")
    print(f"{'='*65}\n")
    return output_path

if __name__=="__main__":
    p=argparse.ArgumentParser(description=f"CrashLens {STATE_NAME} ({STATE_DOT}) — 8-phase normalize+enrich pipeline")
    p.add_argument("--input","-i",required=True); p.add_argument("--output","-o",default=None)
    p.add_argument("--report","-r",default=None)
    p.add_argument("--epdo",default=DEFAULT_EPDO_PRESET,choices=list(EPDO_PRESETS.keys()))
    p.add_argument("--skip-if-normalized",action="store_true")
    p.add_argument("--skip-enrichment",action="store_true",help="Skip Phase 8 (Tier 1 flags + Tier 2 OSM)")
    a=p.parse_args()
    try: normalize(a.input,a.output,a.epdo,a.skip_if_normalized,a.report,a.skip_enrichment)
    except Exception as e: print(f"\n  Error: {e}",file=sys.stderr); raise SystemExit(1)
