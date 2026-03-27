#!/bin/bash
# ==============================================================================
# run_nationwide.sh — One script to download everything
# ==============================================================================
# Run inside a screen session on your Hostinger VPS:
#
#   screen -S nationwide
#   bash run_nationwide.sh
#   # Press Ctrl+A, then D to detach
#   # Close terminal. Come back anytime: screen -r nationwide
# ==============================================================================

set -e  # Stop on errors

LOG_DIR="/opt/crashlens/logs"
mkdir -p "$LOG_DIR"

# ── Ensure credentials are set ──
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$R2_ENDPOINT" ]; then
  echo "❌ R2 credentials not set. Run: source ~/.bashrc"
  exit 1
fi

cd /opt/crashlens/repo
source venv/bin/activate
git pull  # Get latest code

# ── State list (ordered small → large) ──
ALL_STATES="dc ri de ct nj nh vt ma md hi me wv sc nc ky ar ms al la ia ok ks ne nd sd wy nm id nv ut az co va oh pa il mi ga wi mn mo fl ny wa or tn tx ca ak"

# ── Mapillary target states (your current + planned) ──
MAPILLARY_STATES="de va md co"

echo "═══════════════════════════════════════════════════════════"
echo "  CrashLens Nationwide Data Generation"
echo "  Started: $(date)"
echo "  States: $(echo $ALL_STATES | wc -w)"
echo "═══════════════════════════════════════════════════════════"

# ──────────────────────────────────────────────────────────────
# PHASE 1: OSM Roads + Intersections + POIs (all states)
# ──────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  PHASE 1: OSM Cache Generation          ║"
echo "╚══════════════════════════════════════════╝"

for STATE in $ALL_STATES; do
  # Skip if already uploaded
  ABBR=$(echo $STATE | head -c 2)
  if aws s3 ls "s3://crash-lens-data/$STATE/cache/${ABBR}_roads.parquet.gz" \
      --endpoint-url "$R2_ENDPOINT" 2>/dev/null | grep -q parquet; then
    echo "  ⏭️  $STATE — OSM cache exists in R2, skipping"
    continue
  fi

  echo ""
  echo "  ▶ $STATE — $(date '+%H:%M:%S')"
  python generate_osm_data.py --state $STATE --upload \
    2>&1 | tee -a "$LOG_DIR/osm_${STATE}.log"

  echo "  ✅ $STATE OSM done — $(date '+%H:%M:%S')" >> "$LOG_DIR/progress.txt"

  # Clean up disk after upload
  rm -f cache/${ABBR}_roads.parquet cache/${ABBR}_intersections.parquet cache/${ABBR}_pois.parquet
done

echo "PHASE 1 COMPLETE: $(date)" >> "$LOG_DIR/progress.txt"

# ──────────────────────────────────────────────────────────────
# PHASE 2: HPMS Federal Road Data (all states)
# ──────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  PHASE 2: HPMS Federal Data             ║"
echo "╚══════════════════════════════════════════╝"

for STATE in $ALL_STATES; do
  ABBR=$(echo $STATE | head -c 2)
  if aws s3 ls "s3://crash-lens-data/$STATE/cache/${ABBR}_hpms.parquet.gz" \
      --endpoint-url "$R2_ENDPOINT" 2>/dev/null | grep -q parquet; then
    echo "  ⏭️  $STATE — HPMS cache exists, skipping"
    continue
  fi

  echo "  ▶ $STATE HPMS — $(date '+%H:%M:%S')"
  python generate_hpms_data.py --state $STATE --upload \
    2>&1 | tee -a "$LOG_DIR/hpms_${STATE}.log" || true

  echo "  ✅ $STATE HPMS done" >> "$LOG_DIR/progress.txt"
done

echo "PHASE 2 COMPLETE: $(date)" >> "$LOG_DIR/progress.txt"

# ──────────────────────────────────────────────────────────────
# PHASE 3: Federal Safety Data (all states)
# ──────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  PHASE 3: Federal Safety Data           ║"
echo "╚══════════════════════════════════════════╝"

for STATE in $ALL_STATES; do
  ABBR=$(echo $STATE | head -c 2)
  if aws s3 ls "s3://crash-lens-data/$STATE/cache/${ABBR}_schools.parquet.gz" \
      --endpoint-url "$R2_ENDPOINT" 2>/dev/null | grep -q parquet; then
    echo "  ⏭️  $STATE — Federal cache exists, skipping"
    continue
  fi

  echo "  ▶ $STATE Federal — $(date '+%H:%M:%S')"
  python generate_federal_data.py --state $STATE --upload \
    2>&1 | tee -a "$LOG_DIR/federal_${STATE}.log" || true

  echo "  ✅ $STATE Federal done" >> "$LOG_DIR/progress.txt"
done

echo "PHASE 3 COMPLETE: $(date)" >> "$LOG_DIR/progress.txt"

# ──────────────────────────────────────────────────────────────
# PHASE 4: Mapillary Traffic Inventory (target states only)
# ──────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  PHASE 4: Mapillary Traffic Inventory   ║"
echo "╚══════════════════════════════════════════╝"

if [ -z "$MAPILLARY_TOKEN" ]; then
  echo "  ⚠️  MAPILLARY_TOKEN not set — skipping Phase 4"
  echo "  Set it: export MAPILLARY_TOKEN=MLY|..."
else
  for STATE in $MAPILLARY_STATES; do
    ABBR=$(echo $STATE | head -c 2)
    if aws s3 ls "s3://crash-lens-data/$STATE/cache/${ABBR}_mapillary.parquet.gz" \
        --endpoint-url "$R2_ENDPOINT" 2>/dev/null | grep -q parquet; then
      echo "  ⏭️  $STATE — Mapillary cache exists, skipping"
      continue
    fi

    echo "  ▶ $STATE Mapillary — $(date '+%H:%M:%S')"
    python generate_mapillary_data.py \
      --state $ABBR \
      --token "$MAPILLARY_TOKEN" \
      --cache-dir cache \
      --upload \
      2>&1 | tee -a "$LOG_DIR/mapillary_${STATE}.log" || true

    echo "  ✅ $STATE Mapillary done" >> "$LOG_DIR/progress.txt"
    rm -f cache/${ABBR}_mapillary.parquet cache/${ABBR}_mapillary.csv
  done
fi

echo "PHASE 4 COMPLETE: $(date)" >> "$LOG_DIR/progress.txt"

# ──────────────────────────────────────────────────────────────
# DONE
# ──────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  ALL PHASES COMPLETE — $(date)"
echo "  Check progress: cat $LOG_DIR/progress.txt"
echo "  Check R2: aws s3 ls s3://crash-lens-data/ --endpoint-url \$R2_ENDPOINT"
echo "═══════════════════════════════════════════════════════════"
