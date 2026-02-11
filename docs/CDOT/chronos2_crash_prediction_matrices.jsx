import { useState } from "react";

const MATRICES = [
  {
    id: "m1",
    num: "01",
    title: "Total Crash Frequency Forecast",
    subtitle: "Covariate-Informed Univariate — Weekly County-Wide",
    icon: "📈",
    tag: "UNIVARIATE + COVARIATES",
    tagColor: "#00C9A7",
    description: "Forecast total weekly crash count for Douglas County using Chronos 2's covariate-informed mode. Weather, seasonality, and construction serve as known future covariates to dramatically improve accuracy over pure univariate.",
    engineerValue: "Answer: 'How many crashes should we expect next month?' for resource planning, budget justification, and performance tracking against SHSP targets.",
    timeSeriesDesign: {
      granularity: "Weekly (W)",
      contextLength: "260 weeks (Jan 2021 – Nov 2025)",
      forecastHorizon: "12–52 weeks ahead",
      avgPerPeriod: "~95 crashes/week",
    },
    target: {
      column: "COUNT(*) grouped by week",
      sourceColumns: ["Crash Date"],
      transformation: "df.groupby(pd.Grouper(freq='W'))['Document Nbr'].count()",
      sampleValues: "78, 102, 95, 88, 110, 91...",
    },
    covariates: [
      {
        name: "snow_weather_count",
        type: "Past-only",
        sourceColumn: "Weather Condition",
        transform: "COUNT WHERE Weather Condition = '4. Snow' per week",
        why: "Snow weeks show 1.4× crash multiplier in your data",
      },
      {
        name: "rain_weather_count",
        type: "Past-only",
        sourceColumn: "Weather Condition",
        transform: "COUNT WHERE Weather Condition = '5. Rain' per week",
        why: "Wet surface crashes cluster — 1,638 wet + 1,027 snow in data",
      },
      {
        name: "ice_surface_count",
        type: "Past-only",
        sourceColumn: "Roadway Surface Condition",
        transform: "COUNT WHERE Surface = '5. Ice' per week",
        why: "987 ice crashes — strong seasonal covariate signal",
      },
      {
        name: "dark_unlit_ratio",
        type: "Known future",
        sourceColumn: "Light Condition",
        transform: "Daylight hours by week (astronomical calc — known future)",
        why: "2,529 dark-unlit crashes. Shorter days = more night driving",
      },
      {
        name: "month_sin / month_cos",
        type: "Known future",
        sourceColumn: "Derived from Crash Date",
        transform: "sin(2π × month/12), cos(2π × month/12)",
        why: "Captures seasonal cyclicality without dummy variable explosion",
      },
      {
        name: "holiday_flag",
        type: "Known future (categorical)",
        sourceColumn: "Derived from Crash Date",
        transform: "Binary: 1 if week contains federal holiday",
        why: "Holiday weeks have different crash patterns (travel spikes)",
      },
    ],
    chronos2Code: `import pandas as pd
from chronos import Chronos2Pipeline

# === DATA PREPARATION ===
df = pd.read_csv("douglas_all_roads.csv")
df['date'] = pd.to_datetime(df['Crash Date'], format='%m/%d/%Y')

# Aggregate to weekly time series
weekly = df.groupby(pd.Grouper(key='date', freq='W')).agg(
    target=('Document Nbr', 'count'),
    snow_count=('Weather Condition', lambda x: (x == '4. Snow').sum()),
    rain_count=('Weather Condition', lambda x: (x == '5. Rain').sum()),
    ice_count=('Roadway Surface Condition', lambda x: (x == '5. Ice').sum()),
    night_count=('Night?', lambda x: (x == 'Yes').sum()),
).reset_index()
weekly.rename(columns={'date': 'timestamp'}, inplace=True)
weekly['id'] = 'douglas_county'

# Add known future covariates
weekly['month_sin'] = np.sin(2 * np.pi * weekly['timestamp'].dt.month / 12)
weekly['month_cos'] = np.cos(2 * np.pi * weekly['timestamp'].dt.month / 12)

# === CHRONOS 2 FORECAST ===
pipeline = Chronos2Pipeline.from_pretrained("amazon/chronos-2")
context_df = weekly[['id','timestamp','target','snow_count','month_sin','month_cos']]

# Future covariates (known: month_sin, month_cos for next 12 weeks)
future_dates = pd.date_range(weekly['timestamp'].max(), periods=13, freq='W')[1:]
future_df = pd.DataFrame({
    'id': 'douglas_county',
    'timestamp': future_dates,
    'month_sin': np.sin(2 * np.pi * future_dates.month / 12),
    'month_cos': np.cos(2 * np.pi * future_dates.month / 12),
})

pred = pipeline.predict_df(
    context_df, future_df=future_df,
    prediction_length=12,
    quantile_levels=[0.1, 0.25, 0.5, 0.75, 0.9],
    id_column='id', timestamp_column='timestamp', target='target'
)`,
    outputInterpretation: [
      "Median forecast (q0.5): Best estimate of weekly crash count",
      "80% prediction interval (q0.1 – q0.9): Range for resource planning",
      "If actual exceeds q0.9: Investigate — unusual spike, possible data issue or new hazard",
      "If actual below q0.1: Possible underreporting or positive safety trend",
      "Trend direction: Rising? Falling? Justifies funding requests or validates interventions",
    ],
  },
  {
    id: "m2",
    num: "02",
    title: "Severity-Level Multivariate Forecast",
    subtitle: "Joint K-A-B-C-O Prediction — Multivariate Group",
    icon: "⚠️",
    tag: "MULTIVARIATE",
    tagColor: "#FF6B35",
    description: "Jointly forecast K, A, B, C, O crash counts per week using Chronos 2's multivariate mode with group attention. The model captures the co-evolution between severity levels — when O crashes spike, do K/A follow?",
    engineerValue: "Answer: 'Are fatal and serious injury crashes trending up even if total crashes are flat?' Directly supports Vision Zero reporting and KABCO-weighted EPDO scoring.",
    timeSeriesDesign: {
      granularity: "Monthly (M) — K/A counts too sparse for weekly",
      contextLength: "59 months",
      forecastHorizon: "6–12 months",
      avgPerPeriod: "K≈2/mo, A≈11/mo, B≈33/mo, C≈53/mo, O≈320/mo",
    },
    target: {
      column: "5 co-evolving targets in one group",
      sourceColumns: ["Crash Severity", "K_People", "A_People", "B_People", "C_People"],
      transformation: `monthly.pivot: K_count, A_count, B_count, C_count, O_count`,
      sampleValues: "K:[0,1,3,2], A:[10,6,11,13], B:[26,21,30,37]...",
    },
    covariates: [
      {
        name: "avg_speed_limit",
        type: "Past-only",
        sourceColumn: "_co_tu1_speed_limit",
        transform: "MEAN(speed_limit) per month — proxy for exposure mix",
        why: "Higher avg speed = higher severity probability (your data: 65+ mph → 3.8× K/A)",
      },
      {
        name: "alcohol_count",
        type: "Past-only",
        sourceColumn: "Alcohol?",
        transform: "COUNT WHERE Alcohol? = 'Yes' per month",
        why: "445 alcohol crashes, 5.1× K probability — strong severity predictor",
      },
      {
        name: "pedestrian_count",
        type: "Past-only",
        sourceColumn: "Pedestrian?",
        transform: "COUNT WHERE Pedestrian? = 'Yes' per month",
        why: "166 ped crashes, 8.2× K/A rate — critical severity driver",
      },
      {
        name: "night_ratio",
        type: "Known future",
        sourceColumn: "Night?",
        transform: "Proportion of nighttime hours in month (astronomical)",
        why: "Night crashes have 2.4× higher K/A rate",
      },
    ],
    chronos2Code: `# === MULTIVARIATE SEVERITY FORECAST ===
monthly = df.groupby(pd.Grouper(key='date', freq='M')).agg(
    K_count=('Crash Severity', lambda x: (x=='K').sum()),
    A_count=('Crash Severity', lambda x: (x=='A').sum()),
    B_count=('Crash Severity', lambda x: (x=='B').sum()),
    C_count=('Crash Severity', lambda x: (x=='C').sum()),
    O_count=('Crash Severity', lambda x: (x=='O').sum()),
    avg_speed=('_co_tu1_speed_limit', lambda x: pd.to_numeric(x, errors='coerce').mean()),
    alcohol=('Alcohol?', lambda x: (x=='Yes').sum()),
    ped=('Pedestrian?', lambda x: (x=='Yes').sum()),
).reset_index()

# Reshape for Chronos 2 multivariate: each severity = separate series in same group
context_df = pd.DataFrame()
for sev in ['K_count','A_count','B_count','C_count','O_count']:
    temp = monthly[['date', sev, 'avg_speed', 'alcohol']].copy()
    temp.rename(columns={'date':'timestamp', sev:'target'}, inplace=True)
    temp['id'] = sev  # Each severity is a "variate"
    context_df = pd.concat([context_df, temp])

# All severity series share same group_id → joint modeling
pred = pipeline.predict_df(
    context_df,
    prediction_length=6,
    quantile_levels=[0.1, 0.5, 0.9],
    id_column='id', timestamp_column='timestamp', target='target'
)
# Result: Separate forecast for K, A, B, C, O — jointly modeled`,
    outputInterpretation: [
      "K forecast trending up while total flat → systemic severity problem, speed management needed",
      "A+B forecast > historical average → injury reduction countermeasures failing",
      "K/A prediction interval widening → more volatility in severe crashes, harder to predict",
      "EPDO Score = (K×970 + A×266 + B×55.6 + C×18.7 + O×7.6) × forecast — monetized risk",
      "Compare severity forecast to SHSP targets for Douglas County performance reporting",
    ],
  },
  {
    id: "m3",
    num: "03",
    title: "Corridor-Level Cross-Learning Forecast",
    subtitle: "Multi-Corridor with Cross-Learning — Top 10 Routes",
    icon: "🛣️",
    tag: "CROSS-LEARNING",
    tagColor: "#4169E1",
    description: "Forecast crash counts per corridor using Chronos 2's cross-learning mode. All 10 corridors share information via group attention — patterns learned from I-25 (high-volume) improve predictions for lower-volume corridors like Founders Pkwy.",
    engineerValue: "Answer: 'Which corridor will have the most crashes next quarter?' for corridor-specific funding requests, CDOT safety program submissions, and targeted enforcement deployment.",
    timeSeriesDesign: {
      granularity: "Monthly (M) for all; Weekly (W) for I-25 only",
      contextLength: "59 months (10 concurrent series)",
      forecastHorizon: "6–12 months per corridor",
      avgPerPeriod: "I-25≈88/mo, C-470≈17/mo, Parker≈17/mo, Hwy85≈12/mo...",
    },
    target: {
      column: "COUNT(*) per corridor per month",
      sourceColumns: ["Crash Date", "RTE Name"],
      transformation: "df.groupby(['corridor', pd.Grouper(freq='M')])['Document Nbr'].count()",
      sampleValues: "I-25: [127,106,106,88,...], C-470: [16,14,15,13,...]",
    },
    corridors: [
      { name: "I-25", crashes: 5187, weekly: "20.3/wk", system: "Interstate" },
      { name: "C-470", crashes: 997, weekly: "3.9/wk", system: "Primary" },
      { name: "S Parker Rd", crashes: 985, weekly: "3.9/wk", system: "Primary" },
      { name: "Hwy 85", crashes: 701, weekly: "2.7/wk", system: "Primary" },
      { name: "Lincoln Ave", crashes: 562, weekly: "2.2/wk", system: "NonVDOT secondary" },
      { name: "Founders Pkwy", crashes: 444, weekly: "1.7/wk", system: "NonVDOT secondary" },
      { name: "Hwy 83", crashes: 405, weekly: "1.6/wk", system: "Primary" },
      { name: "E Lincoln Ave", crashes: 363, weekly: "1.4/wk", system: "NonVDOT secondary" },
      { name: "Hwy 86", crashes: 302, weekly: "1.2/wk", system: "Primary" },
      { name: "Ridgegate Pkwy", crashes: 235, weekly: "0.9/wk", system: "NonVDOT secondary" },
    ],
    covariates: [
      {
        name: "system_type",
        type: "Static (categorical)",
        sourceColumn: "SYSTEM",
        transform: "Interstate / Primary / NonVDOT secondary — fixed per corridor",
        why: "System type determines exposure profile. Cross-learning transfers patterns between similar systems.",
      },
      {
        name: "snow_week_flag",
        type: "Past-only",
        sourceColumn: "Weather Condition",
        transform: "1 if any snow crash on corridor that month",
        why: "I-25 snow crashes spike differently than local roads",
      },
      {
        name: "roadway_description",
        type: "Static (categorical)",
        sourceColumn: "Roadway Description",
        transform: "Dominant type per corridor (divided/undivided/barrier)",
        why: "Divided vs undivided corridors have fundamentally different crash patterns",
      },
    ],
    chronos2Code: `# === CORRIDOR CROSS-LEARNING FORECAST ===
corridors = ['I-25','C-470','S PARKER RD','HWY 85','LINCOLN AVE',
             'FOUNDERS PKWY','HWY 83','E LINCOLN AVE','HWY 86','RIDGEGATE PKWY']

df_corridors = df[df['RTE Name'].isin(corridors)].copy()
monthly_corr = df_corridors.groupby(
    ['RTE Name', pd.Grouper(key='date', freq='M')]
).agg(target=('Document Nbr','count')).reset_index()
monthly_corr.rename(columns={'date':'timestamp','RTE Name':'id'}, inplace=True)

# Cross-learning: all corridors in same group → shared patterns
# Chronos 2 group attention learns: "winter spike on I-25 correlates
# with winter spike on C-470" and transfers to lower-data corridors
pred = pipeline.predict_df(
    monthly_corr,
    prediction_length=6,
    quantile_levels=[0.1, 0.5, 0.9],
    id_column='id', timestamp_column='timestamp', target='target'
)
# Result: 10 corridor forecasts, each informed by all corridors`,
    outputInterpretation: [
      "Compare corridors: If I-25 forecast = 90/mo but C-470 = 20/mo, allocate resources proportionally",
      "Rising trend on specific corridor → new development, traffic pattern change, or degrading infrastructure",
      "Cross-learning benefit: Founders Pkwy (only 444 crashes) gets better forecast by borrowing patterns from I-25 (5,187 crashes)",
      "Use corridor forecasts in HSIP grant narrative: 'I-25 is predicted to have X crashes next year without intervention'",
      "Rank corridors by forecasted EPDO to prioritize safety projects",
    ],
  },
  {
    id: "m4",
    num: "04",
    title: "Crash Type Distribution Forecast",
    subtitle: "Multivariate — Rear-End / Angle / ROR / Sideswipe / Ped",
    icon: "💥",
    tag: "MULTIVARIATE",
    tagColor: "#C41E3A",
    description: "Jointly forecast the counts of each crash type per month. As traffic patterns shift (new signals, roundabouts, speed changes), the crash type mix evolves. Predicting the type tells you WHICH countermeasure to deploy.",
    engineerValue: "Answer: 'If angle crashes are predicted to rise 15% on Parker Rd next year, should we install a roundabout or signal?' Links forecast directly to countermeasure selection via CMF Clearinghouse.",
    timeSeriesDesign: {
      granularity: "Monthly (M)",
      contextLength: "59 months × 5 crash types = 5 co-evolving series",
      forecastHorizon: "6–12 months",
      avgPerPeriod: "RearEnd≈147/mo, Angle≈86/mo, FixObj≈62/mo, Sideswipe≈59/mo",
    },
    target: {
      column: "5 crash type counts per month",
      sourceColumns: ["Collision Type", "Crash Date"],
      transformation: "Pivot Collision Type → columns, count per month",
      sampleValues: "RearEnd:[155,130,148,...], Angle:[90,75,85,...]",
    },
    typeMapping: [
      { type: "1. Rear End", shortName: "rear_end", count: 8678, pct: "35.1%", topCountermeasure: "Signal timing, advance warning, backplate reflectors" },
      { type: "2. Angle", shortName: "angle", count: 5064, pct: "20.5%", topCountermeasure: "Roundabout, RCUT, signal install, left-turn phasing" },
      { type: "9. Fixed Object", shortName: "run_off_road", count: 3671, pct: "14.9%", topCountermeasure: "Rumble strips, curve delineation, guardrail, clear zone" },
      { type: "4. Sideswipe Same", shortName: "sideswipe", count: 3477, pct: "14.1%", topCountermeasure: "Lane widening, raised median, pavement markings" },
      { type: "10. Deer/Animal", shortName: "animal", count: 1207, pct: "4.9%", topCountermeasure: "Animal fencing, reflectors, warning signs" },
    ],
    covariates: [
      {
        name: "intersection_ratio",
        type: "Past-only",
        sourceColumn: "Intersection Type",
        transform: "Proportion at intersections (4. Four Approaches / total)",
        why: "Angle crashes concentrate at intersections. More intersection exposure → more angle crashes.",
      },
      {
        name: "speed_flag_count",
        type: "Past-only",
        sourceColumn: "Speed?",
        transform: "COUNT WHERE Speed? = 'Yes' per month",
        why: "1,796 speed-related crashes. Speed correlates with run-off-road type.",
      },
      {
        name: "dark_count",
        type: "Past-only",
        sourceColumn: "Light Condition",
        transform: "COUNT WHERE Light = 'Darkness' per month",
        why: "Run-off-road and animal crashes spike at night",
      },
    ],
    chronos2Code: `# === CRASH TYPE MULTIVARIATE FORECAST ===
type_map = {
    '1. Rear End': 'rear_end',
    '2. Angle': 'angle', 
    '9. Fixed Object - Off Road': 'run_off_road',
    '4. Sideswipe - Same Direction': 'sideswipe',
    '10. Deer/Animal': 'animal'
}
df['crash_type_clean'] = df['Collision Type'].map(type_map)
df_typed = df[df['crash_type_clean'].notna()]

monthly_type = df_typed.groupby(
    ['crash_type_clean', pd.Grouper(key='date', freq='M')]
).agg(target=('Document Nbr','count')).reset_index()
monthly_type.rename(columns={
    'date':'timestamp', 'crash_type_clean':'id'
}, inplace=True)

# Multivariate: all crash types co-evolve (if rear-end rises, angle may fall)
pred = pipeline.predict_df(
    monthly_type,
    prediction_length=6, 
    quantile_levels=[0.1, 0.5, 0.9],
    id_column='id', timestamp_column='timestamp', target='target'
)

# AUTO-LINK TO COUNTERMEASURE:
# If angle forecast rises → recommend CMF for roundabout (CMF=0.52)
# If run_off_road rises → recommend CMF for shoulder rumble strips (CMF=0.85)`,
    outputInterpretation: [
      "Type shifting from rear-end to angle → intersection geometry problem, not just congestion",
      "Run-off-road forecast rising → curve/speed issue, recommend rumble strips (CMF = 0.85)",
      "Animal crashes seasonal spike → deploy animal warning signs Sept–Nov",
      "Auto-generate: 'The predicted crash type mix suggests investing $X in [countermeasure] will reduce Y crashes'",
      "Link each type's CMF from your FHWA CMF Clearinghouse database in CRASH LENS",
    ],
  },
  {
    id: "m5",
    num: "05",
    title: "Contributing Factor Trend Forecast",
    subtitle: "Multivariate — Speed / Alcohol / Ped / Bike / Distracted",
    icon: "🔍",
    tag: "MULTIVARIATE + COVARIATES",
    tagColor: "#8B4513",
    description: "Forecast emerging safety problems BEFORE they become crises. Track the trajectory of speed-related, alcohol, pedestrian, bicycle, and distracted driving crashes. These are the flags in your database that drive targeted enforcement and education programs.",
    engineerValue: "Answer: 'Is our DUI enforcement working? Are pedestrian crashes trending up near new developments?' Directly measures program effectiveness and justifies continuation/expansion of safety programs.",
    timeSeriesDesign: {
      granularity: "Monthly (M)",
      contextLength: "59 months × 5 factors",
      forecastHorizon: "6–12 months",
      avgPerPeriod: "Speed≈30/mo, Night≈102/mo, Alcohol≈8/mo, Ped≈3/mo, Bike≈3/mo",
    },
    target: {
      column: "5 contributing factor counts per month",
      sourceColumns: ["Speed?", "Alcohol?", "Pedestrian?", "Bike?", "Distracted?"],
      transformation: "COUNT WHERE flag = 'Yes' per month for each factor",
      sampleValues: "Speed:[96,92,59,25,...], Alcohol:[9,5,6,10,...], Ped:[0,4,5,5,...]",
    },
    covariates: [
      {
        name: "daylight_hours",
        type: "Known future",
        sourceColumn: "Derived (astronomical calculation)",
        transform: "Hours of daylight per month at lat 39.45°",
        why: "Ped/bike crashes strongly correlate with daylight availability",
      },
      {
        name: "young_driver_count",
        type: "Past-only",
        sourceColumn: "Young?",
        transform: "COUNT WHERE Young? = 'Yes' per month",
        why: "Young drivers overrepresented in speed + distracted crashes",
      },
      {
        name: "senior_driver_count",
        type: "Past-only",
        sourceColumn: "Senior?",
        transform: "COUNT WHERE Senior? = 'Yes' per month",
        why: "Senior drivers overrepresented in angle + ped crashes",
      },
    ],
    chronos2Code: `# === CONTRIBUTING FACTOR TREND FORECAST ===
factors = ['Speed?', 'Alcohol?', 'Pedestrian?', 'Bike?', 'Distracted?']

context_frames = []
for factor in factors:
    monthly_f = df[df[factor]=='Yes'].groupby(
        pd.Grouper(key='date', freq='M')
    ).agg(target=('Document Nbr','count')).reset_index()
    monthly_f.rename(columns={'date':'timestamp'}, inplace=True)
    monthly_f['id'] = factor.replace('?','')
    context_frames.append(monthly_f)

context_df = pd.concat(context_frames)

# Add daylight hours as known future covariate
# (Douglas County lat ≈ 39.45°N)
import ephem  # or manual lookup table
# ... compute daylight hours per month ...

pred = pipeline.predict_df(
    context_df,
    prediction_length=12,
    quantile_levels=[0.1, 0.5, 0.9],
    id_column='id', timestamp_column='timestamp', target='target'
)`,
    outputInterpretation: [
      "Speed forecast declining after speed study → intervention validated",
      "Alcohol forecast flat despite enforcement → need different approach (education, rideshare)",
      "Pedestrian forecast rising → new developments generating walk trips without infrastructure",
      "Bike forecast seasonal peak predicted → time bike safety campaign for spring",
      "Distracted forecast can justify hands-free legislation support",
    ],
  },
  {
    id: "m6",
    num: "06",
    title: "Intersection vs Segment Forecast",
    subtitle: "Multivariate — By Location Type & Intersection Geometry",
    icon: "🔀",
    tag: "MULTIVARIATE + CATEGORICAL COVARIATES",
    tagColor: "#6A0DAD",
    description: "Separately forecast intersection crashes (11,038) vs non-intersection segment crashes (12,369), further broken by intersection type (4-leg, 3-leg, roundabout). Chronos 2's categorical covariate support handles intersection geometry natively.",
    engineerValue: "Answer: 'Are roundabout crashes increasing as we build more roundabouts? Are segment run-off-road crashes seasonal?' Separates geometric solutions from segment solutions.",
    timeSeriesDesign: {
      granularity: "Monthly (M)",
      contextLength: "59 months × 4 location types",
      forecastHorizon: "6–12 months",
      avgPerPeriod: "4-leg≈187/mo, Non-int≈210/mo, 3-leg≈14/mo, Roundabout≈8/mo",
    },
    target: {
      column: "Crash count by Intersection Type per month",
      sourceColumns: ["Intersection Type", "Crash Date"],
      transformation: "Pivot by Intersection Type, count per month",
      sampleValues: "4-leg:[195,180,190,...], Non-int:[220,200,215,...], RAB:[6,8,10,...]",
    },
    locationTypes: [
      { type: "1. Not at Intersection", count: 12369, pct: "50.1%", note: "Segment crashes — run-off-road, sideswipe, animal" },
      { type: "4. Four Approaches", count: 11038, pct: "44.7%", note: "Signalized & stop-controlled — angle, rear-end dominant" },
      { type: "2. Two Approaches", count: 811, pct: "3.3%", note: "T-intersections — angle and turning crashes" },
      { type: "5. Roundabout", count: 484, pct: "2.0%", note: "Rare data gold — most counties lack RAB crash data" },
    ],
    covariates: [
      {
        name: "traffic_control_type",
        type: "Static (categorical)",
        sourceColumn: "Traffic Control Type",
        transform: "Signal / Stop / Yield / None — dominant per intersection type",
        why: "Signal vs stop-controlled 4-leg have completely different crash patterns",
      },
      {
        name: "roadway_alignment",
        type: "Past-only",
        sourceColumn: "Roadway Alignment",
        transform: "Proportion on curves/grades per month (from '2. Curve' + '4. Grade - Curve')",
        why: "4,127 curve/grade crashes. Segment crashes highly alignment-dependent.",
      },
    ],
    chronos2Code: `# === INTERSECTION vs SEGMENT FORECAST ===
int_map = {
    '1. Not at Intersection': 'segment',
    '4. Four Approaches': 'four_leg',
    '2. Two Approaches': 'three_leg',
    '5. Roundabout': 'roundabout'
}
df['loc_type'] = df['Intersection Type'].map(int_map)
df_loc = df[df['loc_type'].notna()]

monthly_loc = df_loc.groupby(
    ['loc_type', pd.Grouper(key='date', freq='M')]
).agg(target=('Document Nbr','count')).reset_index()
monthly_loc.rename(columns={'date':'timestamp','loc_type':'id'}, inplace=True)

pred = pipeline.predict_df(
    monthly_loc,
    prediction_length=6,
    quantile_levels=[0.1, 0.5, 0.9],
    id_column='id', timestamp_column='timestamp', target='target'
)`,
    outputInterpretation: [
      "Roundabout crashes rising → new roundabouts generating learning-curve crashes, need better signing/marking",
      "Segment crashes rising in winter → run-off-road on curves, deploy chevrons and rumble strips",
      "4-leg intersection forecast stable while total rises → new crashes are on segments, not intersections",
      "Compare RAB forecast to 4-leg: If RAB converts reduce 4-leg crashes, quantify the safety benefit",
      "Use intersection type forecast in RSA (Road Safety Audit) prioritization",
    ],
  },
];

const DataFlowDiagram = () => (
  <div style={{ background: "rgba(255,255,255,0.02)", borderRadius: 14, padding: 28, margin: "20px 0", border: "1px solid rgba(255,255,255,0.06)" }}>
    <h3 style={{ margin: "0 0 20px", fontSize: 15, fontWeight: 700, color: "#E8ECF1", letterSpacing: "-0.01em" }}>Your CSV Columns → Chronos 2 Input Pipeline</h3>
    <div style={{ display: "grid", gridTemplateColumns: "1fr 40px 1fr 40px 1fr", gap: 0, alignItems: "center" }}>
      {/* RAW COLUMNS */}
      <div style={{ background: "#1a1f2e", borderRadius: 10, padding: 16, border: "1px solid rgba(255,255,255,0.08)" }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: "#00C9A7", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 }}>Raw CSV Columns Used</div>
        {["Crash Date", "Crash Severity", "Collision Type", "RTE Name", "Weather Condition", "Light Condition", "Roadway Surface Condition", "Intersection Type", "Speed?  Alcohol?  Pedestrian?", "Bike?  Night?  Distracted?", "_co_tu1_speed_limit", "Young?  Senior?", "x, y (coordinates)"].map((c, i) => (
          <div key={i} style={{ fontSize: 11, color: "#8B9DAF", padding: "3px 0", fontFamily: "'IBM Plex Mono', monospace" }}>{c}</div>
        ))}
      </div>
      <div style={{ textAlign: "center", color: "#4A5568", fontSize: 20 }}>→</div>
      {/* AGGREGATION */}
      <div style={{ background: "#1a1f2e", borderRadius: 10, padding: 16, border: "1px solid rgba(255,255,255,0.08)" }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: "#FF6B35", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 }}>Aggregation Layer</div>
        {[
          "Weekly/Monthly COUNT(*)",
          "GROUP BY severity level",
          "GROUP BY corridor (RTE Name)",
          "GROUP BY crash type",
          "GROUP BY contributing factor",
          "GROUP BY intersection type",
          "Compute covariates:",
          "  snow_count, rain_count",
          "  dark_ratio, speed_avg",
          "  month_sin, month_cos",
          "  daylight_hours",
        ].map((c, i) => (
          <div key={i} style={{ fontSize: 11, color: i >= 6 ? "#FF6B35" : "#8B9DAF", padding: "3px 0", fontFamily: "'IBM Plex Mono', monospace" }}>{c}</div>
        ))}
      </div>
      <div style={{ textAlign: "center", color: "#4A5568", fontSize: 20 }}>→</div>
      {/* CHRONOS 2 INPUT */}
      <div style={{ background: "#1a1f2e", borderRadius: 10, padding: 16, border: "1px solid rgba(65,105,225,0.3)" }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: "#4169E1", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 }}>Chronos 2 DataFrame</div>
        {[
          "id: series identifier",
          "timestamp: datetime index",
          "target: crash count value",
          "───── covariates ─────",
          "snow_count (past-only)",
          "ice_count (past-only)",
          "month_sin (known future)",
          "month_cos (known future)",
          "daylight_hrs (known future)",
          "holiday_flag (categorical)",
          "───── output ─────",
          "quantiles: 0.1, 0.5, 0.9",
        ].map((c, i) => (
          <div key={i} style={{ fontSize: 11, color: c.startsWith("─") ? "#4169E1" : "#8B9DAF", padding: "3px 0", fontFamily: "'IBM Plex Mono', monospace", fontWeight: c.startsWith("─") ? 700 : 400 }}>{c}</div>
        ))}
      </div>
    </div>
  </div>
);

// === MAIN COMPONENT ===
export default function Chronos2PredictionMatrices() {
  const [selected, setSelected] = useState("m1");
  const [showCode, setShowCode] = useState(false);
  const [view, setView] = useState("matrices"); // matrices | pipeline | summary

  const matrix = MATRICES.find((m) => m.id === selected);

  return (
    <div style={{ fontFamily: "'DM Sans', 'Segoe UI', sans-serif", background: "#080C14", color: "#E0E4EA", minHeight: "100vh" }}>
      {/* HEADER */}
      <div style={{ background: "linear-gradient(135deg, #080C14 0%, #111827 50%, #080C14 100%)", borderBottom: "1px solid rgba(255,255,255,0.05)", padding: "24px 28px 16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 4 }}>
          <div style={{ background: "linear-gradient(135deg, #FF9900, #FF6600)", width: 38, height: 38, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, fontWeight: 900, color: "#000", letterSpacing: "-0.02em" }}>C2</div>
          <div>
            <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: "#F0F2F5", letterSpacing: "-0.02em" }}>Chronos 2 Crash Prediction Matrices</h1>
            <p style={{ margin: 0, fontSize: 11, color: "#6B7280", letterSpacing: "0.06em", textTransform: "uppercase" }}>Douglas County — 24,702 crashes · 59 months · 260 weeks · 1,790 days</p>
          </div>
        </div>
        <div style={{ display: "flex", gap: 2, marginTop: 14 }}>
          {[{ id: "matrices", label: "6 Prediction Matrices" }, { id: "pipeline", label: "Data Pipeline" }, { id: "summary", label: "Decision Matrix" }].map((tab) => (
            <button key={tab.id} onClick={() => setView(tab.id)} style={{ padding: "7px 16px", borderRadius: "6px 6px 0 0", border: "none", background: view === tab.id ? "rgba(255,153,0,0.1)" : "transparent", color: view === tab.id ? "#FF9900" : "#6B7280", fontSize: 12, fontWeight: view === tab.id ? 600 : 400, cursor: "pointer" }}>
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* PIPELINE VIEW */}
      {view === "pipeline" && (
        <div style={{ padding: "24px 28px", maxWidth: 1000 }}>
          <DataFlowDiagram />
          <div style={{ marginTop: 24, background: "rgba(255,153,0,0.06)", borderRadius: 12, padding: 22, border: "1px solid rgba(255,153,0,0.15)" }}>
            <h3 style={{ margin: "0 0 12px", fontSize: 15, fontWeight: 700, color: "#FF9900" }}>Chronos 2 Advantages for Crash Data</h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              {[
                { feat: "Zero-Shot", desc: "No training needed — pretrained on billions of time series observations. Works immediately on your 59-month crash data." },
                { feat: "Multivariate", desc: "K, A, B, C, O severity levels jointly modeled. Group attention captures: 'when O rises, does K follow?'" },
                { feat: "Covariates", desc: "Weather (snow_count), daylight hours, holidays as KNOWN FUTURE inputs — Chronos 2 natively supports this." },
                { feat: "Cross-Learning", desc: "I-25's 5,187 crashes improve Founders Pkwy's forecast (444 crashes). Low-data corridors borrow strength from high-data ones." },
                { feat: "Probabilistic", desc: "Quantile forecasts (10th, 50th, 90th percentile). Report ranges: 'We expect 85–110 crashes next week (80% CI)'" },
                { feat: "Categorical Covariates", desc: "Intersection Type, System, Roadway Description as categorical inputs — no one-hot encoding needed." },
              ].map((item, i) => (
                <div key={i} style={{ background: "rgba(255,255,255,0.02)", borderRadius: 8, padding: 14 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: "#FF9900", marginBottom: 4 }}>{item.feat}</div>
                  <div style={{ fontSize: 12, color: "#9BA3AE", lineHeight: 1.6 }}>{item.desc}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* SUMMARY / DECISION MATRIX */}
      {view === "summary" && (
        <div style={{ padding: "24px 28px", maxWidth: 1000 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: "#F0F2F5", marginBottom: 4 }}>Decision Matrix: Which Forecast Answers Which Question?</h2>
          <p style={{ fontSize: 13, color: "#6B7280", marginBottom: 20 }}>Match your engineering question to the right Chronos 2 matrix</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <div style={{ display: "grid", gridTemplateColumns: "280px 80px 120px 1fr", gap: 12, padding: "10px 14px", background: "rgba(255,255,255,0.04)", borderRadius: 8 }}>
              {["Engineering Question", "Matrix", "Chronos Mode", "Action Output"].map((h) => (
                <span key={h} style={{ fontSize: 10, fontWeight: 700, color: "#6B7280", textTransform: "uppercase", letterSpacing: "0.08em" }}>{h}</span>
              ))}
            </div>
            {[
              { q: "How many crashes next quarter?", m: "#01", mode: "Univariate+Cov", action: "Budget & resource planning" },
              { q: "Are fatal crashes trending up?", m: "#02", mode: "Multivariate", action: "Vision Zero reporting, SHSP targets" },
              { q: "Which corridor needs attention?", m: "#03", mode: "Cross-Learning", action: "HSIP corridor selection, enforcement" },
              { q: "What crash type to expect?", m: "#04", mode: "Multivariate", action: "Countermeasure selection via CMF" },
              { q: "Is DUI enforcement working?", m: "#05", mode: "Multivariate+Cov", action: "Program evaluation, justify spending" },
              { q: "Intersection or segment problem?", m: "#06", mode: "Multivariate+Cat", action: "RSA prioritization, geometric fixes" },
              { q: "Predict crashes after speed change?", m: "#01+#02", mode: "What-If scenario", action: "Before/after speed study design" },
              { q: "Justify grant application?", m: "#03+#04", mode: "Corridor forecast", action: "HSIP/CDOT narrative with CI ranges" },
              { q: "Deploy enforcement when?", m: "#01+#05", mode: "Temporal forecast", action: "Weekly scheduling by risk window" },
              { q: "Track program effectiveness?", m: "#02+#05", mode: "Trend comparison", action: "Actual vs. predicted counterfactual" },
            ].map((row, i) => (
              <div key={i} style={{ display: "grid", gridTemplateColumns: "280px 80px 120px 1fr", gap: 12, padding: "10px 14px", background: i % 2 === 0 ? "rgba(255,255,255,0.015)" : "transparent", borderRadius: 6, alignItems: "center" }}>
                <span style={{ fontSize: 13, fontWeight: 500, color: "#D0D4DA" }}>{row.q}</span>
                <span style={{ fontSize: 13, fontWeight: 700, color: "#FF9900" }}>{row.m}</span>
                <span style={{ fontSize: 11, color: "#6B7280" }}>{row.mode}</span>
                <span style={{ fontSize: 12, color: "#9BA3AE" }}>{row.action}</span>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 28, background: "rgba(0,201,167,0.06)", borderRadius: 12, padding: 20, border: "1px solid rgba(0,201,167,0.15)" }}>
            <h3 style={{ margin: "0 0 8px", fontSize: 14, fontWeight: 700, color: "#00C9A7" }}>💡 Implementation Priority Order</h3>
            <div style={{ fontSize: 13, color: "#9BA3AE", lineHeight: 1.8 }}>
              <strong style={{ color: "#D0D4DA" }}>Week 1:</strong> Matrix #01 (total forecast) — immediate value, simplest pipeline, proves concept.
              <br /><strong style={{ color: "#D0D4DA" }}>Week 2:</strong> Matrix #03 (corridor forecast) — cross-learning is Chronos 2's killer feature. Direct grant use.
              <br /><strong style={{ color: "#D0D4DA" }}>Week 3:</strong> Matrix #02 + #04 (severity + type) — multivariate. Drives countermeasure automation.
              <br /><strong style={{ color: "#D0D4DA" }}>Week 4:</strong> Matrix #05 + #06 (factors + intersection) — program evaluation and geometric analysis.
            </div>
          </div>
        </div>
      )}

      {/* MATRICES VIEW */}
      {view === "matrices" && (
        <div style={{ display: "flex" }}>
          {/* SIDEBAR */}
          <div style={{ width: 240, flexShrink: 0, borderRight: "1px solid rgba(255,255,255,0.05)", padding: "16px 12px" }}>
            {MATRICES.map((m) => (
              <button key={m.id} onClick={() => { setSelected(m.id); setShowCode(false); }} style={{ width: "100%", textAlign: "left", padding: "10px 12px", marginBottom: 3, borderRadius: 8, border: selected === m.id ? `1px solid ${m.tagColor}33` : "1px solid transparent", background: selected === m.id ? `${m.tagColor}0A` : "transparent", color: selected === m.id ? "#F0F2F5" : "#8B95A0", cursor: "pointer", transition: "all 0.15s" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontSize: 16 }}>{m.icon}</span>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: selected === m.id ? 600 : 500, lineHeight: 1.3 }}>{m.title}</div>
                    <div style={{ fontSize: 9, color: m.tagColor, fontWeight: 600, marginTop: 2, textTransform: "uppercase", letterSpacing: "0.04em" }}>{m.tag}</div>
                  </div>
                </div>
              </button>
            ))}
          </div>

          {/* DETAIL PANEL */}
          <div style={{ flex: 1, padding: "20px 24px", maxHeight: "calc(100vh - 120px)", overflowY: "auto" }}>
            {matrix && (
              <>
                {/* HEADER */}
                <div style={{ display: "flex", alignItems: "flex-start", gap: 14, marginBottom: 16 }}>
                  <div style={{ fontSize: 28, lineHeight: 1 }}>{matrix.icon}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span style={{ fontSize: 13, fontWeight: 800, color: matrix.tagColor, fontFamily: "'IBM Plex Mono', monospace" }}>{matrix.num}</span>
                      <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: "#F0F2F5" }}>{matrix.title}</h2>
                    </div>
                    <p style={{ margin: "2px 0 0", fontSize: 12, color: "#6B7280" }}>{matrix.subtitle}</p>
                  </div>
                  <span style={{ padding: "4px 12px", borderRadius: 16, background: `${matrix.tagColor}15`, color: matrix.tagColor, fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.04em", whiteSpace: "nowrap" }}>{matrix.tag}</span>
                </div>

                {/* DESCRIPTION */}
                <div style={{ background: "rgba(255,255,255,0.025)", borderRadius: 10, padding: "14px 18px", marginBottom: 14, borderLeft: `3px solid ${matrix.tagColor}` }}>
                  <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65, color: "#B0B8C1" }}>{matrix.description}</p>
                </div>

                {/* ENGINEER VALUE */}
                <div style={{ background: `${matrix.tagColor}08`, borderRadius: 10, padding: "12px 16px", marginBottom: 18, border: `1px solid ${matrix.tagColor}18` }}>
                  <span style={{ fontSize: 10, fontWeight: 700, color: matrix.tagColor, textTransform: "uppercase", letterSpacing: "0.08em" }}>🎯 Traffic Engineer Value</span>
                  <p style={{ margin: "6px 0 0", fontSize: 13, color: "#C0C8D0", lineHeight: 1.5 }}>{matrix.engineerValue}</p>
                </div>

                {/* TIME SERIES DESIGN */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 10, marginBottom: 18 }}>
                  {Object.entries(matrix.timeSeriesDesign).map(([key, val]) => (
                    <div key={key} style={{ background: "rgba(255,255,255,0.02)", borderRadius: 8, padding: "10px 12px", textAlign: "center" }}>
                      <div style={{ fontSize: 9, fontWeight: 700, color: "#6B7280", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>{key.replace(/([A-Z])/g, " $1")}</div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: "#D0D4DA" }}>{val}</div>
                    </div>
                  ))}
                </div>

                {/* TARGET DEFINITION */}
                <div style={{ marginBottom: 18 }}>
                  <h3 style={{ fontSize: 12, fontWeight: 700, color: "#8B95A0", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>Target Variable (what Chronos 2 predicts)</h3>
                  <div style={{ background: "#111827", borderRadius: 10, padding: 14, border: "1px solid rgba(255,255,255,0.06)" }}>
                    <div style={{ display: "grid", gridTemplateColumns: "100px 1fr", gap: "6px 12px" }}>
                      <span style={{ fontSize: 11, color: "#6B7280", fontWeight: 600 }}>Column:</span>
                      <code style={{ fontSize: 12, color: "#FF9900", fontFamily: "'IBM Plex Mono', monospace" }}>{matrix.target.column}</code>
                      <span style={{ fontSize: 11, color: "#6B7280", fontWeight: 600 }}>Source:</span>
                      <code style={{ fontSize: 12, color: "#8B9DAF", fontFamily: "'IBM Plex Mono', monospace" }}>{matrix.target.sourceColumns.join(", ")}</code>
                      <span style={{ fontSize: 11, color: "#6B7280", fontWeight: 600 }}>Transform:</span>
                      <code style={{ fontSize: 12, color: "#8B9DAF", fontFamily: "'IBM Plex Mono', monospace" }}>{matrix.target.transformation}</code>
                      <span style={{ fontSize: 11, color: "#6B7280", fontWeight: 600 }}>Sample:</span>
                      <code style={{ fontSize: 11, color: "#6B7280", fontFamily: "'IBM Plex Mono', monospace" }}>{matrix.target.sampleValues}</code>
                    </div>
                  </div>
                </div>

                {/* COVARIATES */}
                <div style={{ marginBottom: 18 }}>
                  <h3 style={{ fontSize: 12, fontWeight: 700, color: "#8B95A0", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>Covariates (additional inputs to Chronos 2)</h3>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {matrix.covariates.map((cov, i) => (
                      <div key={i} style={{ background: "rgba(255,255,255,0.02)", borderRadius: 8, padding: "10px 14px", display: "grid", gridTemplateColumns: "160px 90px 1fr", gap: 10, alignItems: "start" }}>
                        <div>
                          <code style={{ fontSize: 12, fontWeight: 600, color: "#D0D4DA", fontFamily: "'IBM Plex Mono', monospace" }}>{cov.name}</code>
                          <div style={{ fontSize: 10, color: cov.type.includes("Known") ? "#00C9A7" : cov.type.includes("Static") ? "#8B8BFF" : "#FF9900", marginTop: 2, fontWeight: 600 }}>{cov.type}</div>
                        </div>
                        <code style={{ fontSize: 10, color: "#6B7280", fontFamily: "'IBM Plex Mono', monospace" }}>{cov.sourceColumn}</code>
                        <div>
                          <div style={{ fontSize: 11, color: "#8B9DAF", marginBottom: 2 }}>{cov.transform}</div>
                          <div style={{ fontSize: 11, color: "#6B7280", fontStyle: "italic" }}>{cov.why}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* CORRIDORS TABLE (Matrix 3) */}
                {matrix.corridors && (
                  <div style={{ marginBottom: 18 }}>
                    <h3 style={{ fontSize: 12, fontWeight: 700, color: "#8B95A0", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>Cross-Learning Corridors (10 concurrent time series)</h3>
                    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                      {matrix.corridors.map((c, i) => (
                        <div key={i} style={{ display: "grid", gridTemplateColumns: "140px 80px 80px 100px", gap: 10, padding: "8px 12px", background: i % 2 === 0 ? "rgba(255,255,255,0.015)" : "transparent", borderRadius: 6, alignItems: "center" }}>
                          <span style={{ fontSize: 13, fontWeight: 600, color: "#D0D4DA" }}>{c.name}</span>
                          <span style={{ fontSize: 12, fontWeight: 700, color: "#4169E1" }}>{c.crashes.toLocaleString()}</span>
                          <span style={{ fontSize: 11, color: "#6B7280" }}>{c.weekly}</span>
                          <span style={{ fontSize: 10, color: "#8B95A0" }}>{c.system}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* CRASH TYPE MAPPING (Matrix 4) */}
                {matrix.typeMapping && (
                  <div style={{ marginBottom: 18 }}>
                    <h3 style={{ fontSize: 12, fontWeight: 700, color: "#8B95A0", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>Crash Type → Countermeasure Auto-Link</h3>
                    {matrix.typeMapping.map((t, i) => (
                      <div key={i} style={{ display: "grid", gridTemplateColumns: "200px 60px 1fr", gap: 10, padding: "8px 12px", background: i % 2 === 0 ? "rgba(255,255,255,0.015)" : "transparent", borderRadius: 6, alignItems: "center", marginBottom: 2 }}>
                        <div>
                          <span style={{ fontSize: 12, fontWeight: 600, color: "#D0D4DA" }}>{t.type}</span>
                          <span style={{ fontSize: 10, color: "#6B7280", marginLeft: 8 }}>({t.pct})</span>
                        </div>
                        <span style={{ fontSize: 12, fontWeight: 700, color: "#C41E3A" }}>{t.count.toLocaleString()}</span>
                        <span style={{ fontSize: 11, color: "#8B9DAF" }}>{t.topCountermeasure}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* LOCATION TYPES (Matrix 6) */}
                {matrix.locationTypes && (
                  <div style={{ marginBottom: 18 }}>
                    <h3 style={{ fontSize: 12, fontWeight: 700, color: "#8B95A0", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>Location Type Distribution</h3>
                    {matrix.locationTypes.map((l, i) => (
                      <div key={i} style={{ display: "grid", gridTemplateColumns: "200px 70px 50px 1fr", gap: 10, padding: "8px 12px", background: i % 2 === 0 ? "rgba(255,255,255,0.015)" : "transparent", borderRadius: 6, alignItems: "center", marginBottom: 2 }}>
                        <span style={{ fontSize: 12, fontWeight: 600, color: "#D0D4DA" }}>{l.type}</span>
                        <span style={{ fontSize: 12, fontWeight: 700, color: "#6A0DAD" }}>{l.count.toLocaleString()}</span>
                        <span style={{ fontSize: 11, color: "#6B7280" }}>{l.pct}</span>
                        <span style={{ fontSize: 11, color: "#8B9DAF" }}>{l.note}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* CODE TOGGLE */}
                <div style={{ marginBottom: 18 }}>
                  <button onClick={() => setShowCode(!showCode)} style={{ padding: "8px 18px", borderRadius: 8, border: "1px solid rgba(255,153,0,0.3)", background: showCode ? "rgba(255,153,0,0.1)" : "transparent", color: "#FF9900", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
                    {showCode ? "▼" : "▶"} Chronos 2 Python Code
                  </button>
                  {showCode && (
                    <pre style={{ marginTop: 10, background: "#0D1117", borderRadius: 10, padding: 18, fontSize: 11, lineHeight: 1.6, color: "#C9D1D9", fontFamily: "'IBM Plex Mono', monospace", overflowX: "auto", border: "1px solid rgba(255,255,255,0.06)" }}>
                      {matrix.chronos2Code}
                    </pre>
                  )}
                </div>

                {/* OUTPUT INTERPRETATION */}
                <div style={{ background: "rgba(0,201,167,0.05)", borderRadius: 10, padding: "14px 18px", border: "1px solid rgba(0,201,167,0.12)" }}>
                  <span style={{ fontSize: 10, fontWeight: 700, color: "#00C9A7", textTransform: "uppercase", letterSpacing: "0.08em" }}>📊 How to Read the Output (for Traffic Engineers)</span>
                  <div style={{ marginTop: 8 }}>
                    {matrix.outputInterpretation.map((item, i) => (
                      <div key={i} style={{ fontSize: 12, color: "#9BA3AE", padding: "4px 0", lineHeight: 1.55, display: "flex", gap: 8 }}>
                        <span style={{ color: "#00C9A7", flexShrink: 0 }}>→</span>
                        {item}
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
