#!/bin/bash
# ==============================================================================
# CrashLens VPS Setup — Run OSM + Mapillary Downloads on Hostinger VPS
# ==============================================================================
#
# PURPOSE: GitHub Actions has a 6-hour timeout. Large states (VA, TX, CA)
# need 12-72 hours for OSM/Mapillary downloads. Run on VPS instead.
#
# TOOL: GNU Screen — keeps commands running after you close the terminal.
# Your laptop can sleep, disconnect, whatever — the VPS keeps working.
#
# ==============================================================================

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: SSH into your Hostinger VPS
# ═══════════════════════════════════════════════════════════════════════════════
#
# From your computer terminal:
#   ssh root@YOUR_VPS_IP
#
# Or from Hostinger dashboard:
#   VPS → Manage → Terminal (browser-based SSH)
#
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: One-time server setup (run this once)
# ═══════════════════════════════════════════════════════════════════════════════

# Update system
apt update && apt upgrade -y

# Install Python + tools
apt install -y python3 python3-pip python3-venv screen git awscli

# Install screen (the magic tool that keeps commands running)
# Screen is usually pre-installed, but just in case:
apt install -y screen

# Create working directory
mkdir -p /opt/crashlens
cd /opt/crashlens

# Clone your repo
git clone https://github.com/ecomhub200/Douglas_County_2.git repo
cd repo

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install all dependencies
pip install pandas pyarrow requests osmnx scipy geopandas shapely duckdb numpy

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3: Configure R2 credentials (run this once)
# ═══════════════════════════════════════════════════════════════════════════════

# Set R2 credentials (same ones from GitHub Secrets)
cat >> ~/.bashrc << 'ENVEOF'
# CrashLens R2 credentials
export AWS_ACCESS_KEY_ID="YOUR_CF_R2_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="YOUR_CF_R2_SECRET_ACCESS_KEY"
export AWS_DEFAULT_REGION="auto"
export CF_ACCOUNT_ID="YOUR_CF_ACCOUNT_ID"
export R2_ENDPOINT="https://YOUR_CF_ACCOUNT_ID.r2.cloudflarestorage.com"

# Mapillary token
export MAPILLARY_TOKEN="MLY|YOUR_TOKEN_HERE"
ENVEOF

# Load the credentials
source ~/.bashrc

# Test R2 connection
aws s3 ls s3://crash-lens-data/ --endpoint-url "$R2_ENDPOINT" --max-items 5

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4: HOW TO USE SCREEN (the key to 3-day runs)
# ═══════════════════════════════════════════════════════════════════════════════
#
# SCREEN CHEAT SHEET:
#
#   screen -S osm          Create a new screen session named "osm"
#   [run your command]     Start the long-running download
#   Ctrl+A, then D         DETACH from screen (command keeps running!)
#   exit / close terminal  SAFE — screen keeps running on VPS
#
#   screen -ls             List all running screens
#   screen -r osm          RE-ATTACH to see progress
#   Ctrl+A, then D         Detach again
#
#   screen -X -S osm quit  Kill a screen session (if needed)
#
# FLOW:
#   1. SSH into VPS
#   2. screen -S osm       (create session)
#   3. Run command          (starts downloading)
#   4. Ctrl+A, D           (detach — command keeps running)
#   5. Close laptop, go to sleep
#   6. Next day: SSH in, screen -r osm (check progress)
#
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5: RUN OSM NATIONWIDE (all 51 states)
# ═══════════════════════════════════════════════════════════════════════════════

# SSH into VPS, then:

cd /opt/crashlens/repo
source venv/bin/activate

# Create a screen session for OSM
screen -S osm

# Run ALL states one by one (takes 2-3 days total)
# The script handles each state, uploads to R2, then moves to next
for STATE in dc ri de ct nj nh vt ma md hi me wv sc nc ky ar ms al la in ia ok ks ne nd sd wy nm id nv ut az wy co va oh pa il mi ga wi mn mo fl ny wa or tn tx ca ak; do
  echo ""
  echo "════════════════════════════════════════"
  echo "  Starting: $STATE — $(date)"
  echo "════════════════════════════════════════"
  python generate_osm_data.py --state $STATE --upload 2>&1 | tee -a /opt/crashlens/osm_log.txt
  echo "$STATE done at $(date)" >> /opt/crashlens/osm_progress.txt
done

echo "ALL STATES COMPLETE at $(date)" >> /opt/crashlens/osm_progress.txt

# NOW DETACH: press Ctrl+A, then D
# You'll see: [detached from osm]
# Close your terminal. Go to sleep. The download continues.

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 6: RUN MAPILLARY STATEWIDE (one state at a time)
# ═══════════════════════════════════════════════════════════════════════════════

# Open a NEW screen session (can run parallel with OSM)
screen -S mapillary

cd /opt/crashlens/repo
source venv/bin/activate

# Download Mapillary for specific states
for STATE in de va md co; do
  echo ""
  echo "════════════════════════════════════════"
  echo "  Mapillary: $STATE — $(date)"
  echo "════════════════════════════════════════"
  python generate_mapillary_data.py \
    --state $STATE \
    --token "$MAPILLARY_TOKEN" \
    --cache-dir cache \
    --upload \
    2>&1 | tee -a /opt/crashlens/mapillary_log.txt
  echo "$STATE done at $(date)" >> /opt/crashlens/mapillary_progress.txt
done

# Detach: Ctrl+A, then D

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 7: RUN HPMS + FEDERAL DATA
# ═══════════════════════════════════════════════════════════════════════════════

screen -S hpms

cd /opt/crashlens/repo
source venv/bin/activate

for STATE in de va md co; do
  python generate_hpms_data.py --state $STATE --upload 2>&1 | tee -a /opt/crashlens/hpms_log.txt
  python generate_federal_data.py --state $STATE --upload 2>&1 | tee -a /opt/crashlens/federal_log.txt
done

# Detach: Ctrl+A, then D

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 8: BUILD ROAD DATABASES (after OSM + HPMS + Mapillary finish)
# ═══════════════════════════════════════════════════════════════════════════════

screen -S roaddb

cd /opt/crashlens/repo
source venv/bin/activate

for STATE in de va md co; do
  # First download all caches from R2
  ABBR=$(echo $STATE | head -c 2)
  mkdir -p cache
  for FILE in ${ABBR}_roads.parquet.gz ${ABBR}_intersections.parquet.gz ${ABBR}_hpms.parquet.gz ${ABBR}_pois.parquet.gz ${ABBR}_schools.parquet.gz ${ABBR}_bridges.parquet.gz ${ABBR}_rail_crossings.parquet.gz ${ABBR}_transit.parquet.gz ${ABBR}_mapillary.parquet.gz; do
    aws s3 cp "s3://crash-lens-data/$STATE/cache/$FILE" "cache/$FILE" \
      --endpoint-url "$R2_ENDPOINT" --only-show-errors 2>/dev/null && \
      gunzip -f "cache/$FILE" && echo "  ✅ $FILE"
  done

  python generate_road_database.py --state $ABBR --cache-dir cache --upload
  rm -f cache/*.parquet  # Clean up for next state
done

# Detach: Ctrl+A, then D

# ═══════════════════════════════════════════════════════════════════════════════
# MONITORING: Check progress from anywhere
# ═══════════════════════════════════════════════════════════════════════════════
#
# SSH into VPS at any time:
#
#   screen -ls                    See all running sessions
#   screen -r osm                 Attach to OSM session (see live output)
#   screen -r mapillary           Attach to Mapillary session
#   Ctrl+A, D                     Detach (back to main terminal)
#
#   cat /opt/crashlens/osm_progress.txt        See which states are done
#   cat /opt/crashlens/mapillary_progress.txt   See Mapillary progress
#   tail -20 /opt/crashlens/osm_log.txt        See last 20 lines of log
#
#   # Check R2 for uploaded files:
#   aws s3 ls s3://crash-lens-data/virginia/cache/ --endpoint-url "$R2_ENDPOINT"
#
# ═══════════════════════════════════════════════════════════════════════════════
# ESTIMATED TIMES (Hostinger VPS — 2 vCPU, 4GB RAM)
# ═══════════════════════════════════════════════════════════════════════════════
#
#   OSM Cache Generation (per state):
#     Small (DE, RI, DC):     5-10 min
#     Medium (MD, VA, CO):    30-90 min
#     Large (TX, CA, NY):     3-8 hours
#     ALL 51 states:          ~48-72 hours
#
#   Mapillary Download (per state):
#     Small (DE):             3-5 min
#     Medium (VA):            60-90 min
#     Large (TX):             6-10 hours
#     Large (CA):             8-12 hours
#
#   HPMS Download (per state):
#     All states:             5-15 min each
#     ALL 51 states:          ~8-12 hours
#
#   Road Database Build (per state):
#     All states:             5-30 sec each
#     ALL states:             ~30 min total
#
#   TOTAL for nationwide:     ~3-4 days (parallel: OSM + Mapillary + HPMS)
#
# ═══════════════════════════════════════════════════════════════════════════════
# TROUBLESHOOTING
# ═══════════════════════════════════════════════════════════════════════════════
#
#   Q: "screen: command not found"
#   A: apt install screen
#
#   Q: "Permission denied" on SSH
#   A: Check Hostinger dashboard for correct IP and password
#
#   Q: Script crashed mid-run
#   A: screen -r osm → see the error → fix → re-run from that state
#      The for loop will re-process all states, but --upload skips
#      states that already have data in R2 (check with aws s3 ls)
#
#   Q: VPS ran out of disk space
#   A: rm -rf cache/*.parquet after each state uploads to R2
#      Or: df -h to check space, apt autoremove to free up
#
#   Q: "Killed" during osmnx download (OOM)
#   A: Your VPS needs 4GB+ RAM for large states.
#      Or add swap: fallocate -l 4G /swapfile && chmod 600 /swapfile && \
#         mkswap /swapfile && swapon /swapfile
#
# ═══════════════════════════════════════════════════════════════════════════════
