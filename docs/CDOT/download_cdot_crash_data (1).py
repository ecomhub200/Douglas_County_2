#!/usr/bin/env python3
"""
CDOT OnBase Crash Data Downloader — Autonomous Pipeline
========================================================
Downloads crash data from Colorado DOT's Hyland OnBase portal.

LIFECYCLE:
  - Preliminary data updates monthly (same doc_id, rows grow each month)
  - A year stays "preliminary" until a NEWER year appears in the manifest
  - Only when 2026 preliminary is added does 2025 become "finalized"
  - Finalized years are never re-downloaded (unless --force)

Usage:
  python download_cdot_crash_data.py --data-dir data/CDOT --jurisdiction douglas --latest
  python download_cdot_crash_data.py --data-dir data/CDOT --jurisdiction douglas --force
  python download_cdot_crash_data.py --discover
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

BASE_URL = "https://oitco.hylandcloud.com/CDOTRMPop/docpop/docpop.aspx"
MANIFEST_FILE = "cdot_manifest.json"

JURISDICTIONS = {
    "douglas": "DOUGLAS", "denver": "DENVER", "jefferson": "JEFFERSON",
    "arapahoe": "ARAPAHOE", "adams": "ADAMS", "boulder": "BOULDER",
    "el paso": "EL PASO", "larimer": "LARIMER", "weld": "WELD",
    "pueblo": "PUEBLO", "broomfield": "BROOMFIELD",
}


# ═══════════════════════════════════════════════════════════════════
# MANIFEST
# ═══════════════════════════════════════════════════════════════════

def load_manifest(data_dir: Path) -> tuple:
    """Load manifest from repo root or data dir."""
    for loc in [Path(MANIFEST_FILE), data_dir / MANIFEST_FILE]:
        if loc.exists():
            return json.loads(loc.read_text()), loc
    manifest = {
        "source": "CDOT OnBase",
        "portal_url": BASE_URL,
        "data_dictionary": {"doc_id": "17470635"},
        "years": {},
    }
    path = data_dir / MANIFEST_FILE
    path.write_text(json.dumps(manifest, indent=2))
    return manifest, path


def save_manifest(manifest: dict, path: Path):
    manifest["last_updated"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(manifest, indent=2))
    logger.info(f"  Manifest saved: {path}")


# ═══════════════════════════════════════════════════════════════════
# PLAYWRIGHT DOWNLOAD (proven working via OleHandler.ashx)
# ═══════════════════════════════════════════════════════════════════

def download_from_onbase(doc_id: str, output_path: Path, headless: bool = True,
                         timeout_sec: int = 90) -> bool:
    """
    Download a document from OnBase using Playwright.
    OleHandler.ashx triggers a browser download — we capture it.
    """
    from playwright.sync_api import sync_playwright

    output_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"{BASE_URL}?clienttype=html&docid={doc_id}"
    logger.info(f"  Playwright: opening docid={doc_id}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=ProtocolHandlerPermissionPrompt",
                "--disable-external-intent-requests",
            ],
        )
        context = browser.new_context(
            accept_downloads=True,
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        captured = {}

        def on_download(download):
            logger.info(f"  Download event: {download.suggested_filename}")
            try:
                download.save_as(str(output_path))
                captured["ok"] = True
                captured["filename"] = download.suggested_filename
            except Exception as e:
                logger.error(f"  Download save failed: {e}")
                captured["error"] = str(e)

        page.on("download", on_download)
        page.on("dialog", lambda d: d.accept())

        # Establish session
        page.goto(BASE_URL, wait_until="networkidle", timeout=30_000)
        page.wait_for_timeout(1000)

        # Navigate — OleHandler.ashx fires download automatically
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)

        for _ in range(timeout_sec):
            if captured.get("ok"):
                break
            page.wait_for_timeout(1000)

        browser.close()

        if captured.get("ok") and output_path.exists():
            size = output_path.stat().st_size
            if size > 500:
                logger.info(f"  ✓ Downloaded {size:,} bytes ({captured.get('filename')})")
                return True
        logger.error(f"  ✗ Download failed: {captured.get('error', 'no download event')}")
        return False


# ═══════════════════════════════════════════════════════════════════
# AUTO-DISCOVERY
# ═══════════════════════════════════════════════════════════════════

def discover_crash_listings(headless: bool = True) -> list:
    """Browse OnBase DocPop to find crash listing documents."""
    from playwright.sync_api import sync_playwright

    logger.info("Auto-discovery: Browsing OnBase for crash listings...")
    found = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        try:
            page.goto(BASE_URL, wait_until="networkidle", timeout=30_000)
            page.wait_for_timeout(2000)

            for frame in page.frames:
                try:
                    links = frame.evaluate("""() => {
                        const results = [];
                        document.querySelectorAll('a[href*="docid"], a[href*="docId"]').forEach(a => {
                            const match = (a.href || '').match(/docid=(\\d+)/i);
                            if (match) results.push({
                                doc_id: match[1], title: a.textContent.trim()
                            });
                        });
                        document.querySelectorAll('tr').forEach(tr => {
                            const text = tr.textContent || '';
                            if (text.toLowerCase().includes('crash listing')) {
                                const idMatch = text.match(/(\\d{7,9})/);
                                if (idMatch) results.push({
                                    doc_id: idMatch[1], title: text.trim().substring(0, 200)
                                });
                            }
                        });
                        return results;
                    }""")
                    found.extend([l for l in links if l.get("doc_id")])
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"  Discovery failed: {e}")
        finally:
            browser.close()

    seen = set()
    unique = []
    for item in found:
        did = item.get("doc_id")
        if did and did not in seen:
            seen.add(did)
            year_match = re.search(r'20\d{2}', item.get("title", ""))
            item["year"] = year_match.group(0) if year_match else None
            unique.append(item)
            logger.info(f"  Found: docid={did} year={item['year']} title={item.get('title', '')[:80]}")
    return unique


def check_for_new_year(manifest: dict, data_dir: Path, headless: bool = True) -> bool:
    """Check if CDOT published new year data. Returns True if manifest updated."""
    known_years = set(manifest.get("years", {}).keys())
    logger.info(f"Checking for new data (known years: {', '.join(sorted(known_years))})")

    discovered = discover_crash_listings(headless)
    updated = False
    for item in discovered:
        year = item.get("year")
        doc_id = item.get("doc_id")
        if year and doc_id and year not in known_years:
            logger.info(f"  🆕 New year discovered: {year} (docid={doc_id})")
            manifest["years"][year] = {
                "doc_id": doc_id,
                "status": "preliminary",
                "label": item.get("title", f"Crash Listing {year}"),
                "discovered": datetime.now(timezone.utc).isoformat(),
            }
            # NOW we can finalize the previous year — a newer one exists
            prev = str(int(year) - 1)
            if prev in manifest["years"] and manifest["years"][prev].get("status") == "preliminary":
                manifest["years"][prev]["status"] = "finalized"
                logger.info(f"  {prev} → finalized (newer year {year} exists)")
            updated = True

    if not updated:
        logger.info("  No new years found via auto-discovery.")
        current_year = datetime.now(timezone.utc).year
        if str(current_year) not in known_years and datetime.now(timezone.utc).month >= 3:
            _queue_github_issue(
                f"CDOT {current_year} crash data not found",
                f"Auto-discovery could not find {current_year} crash listing.\n\n"
                f"**Manual steps:**\n"
                f"1. Visit {BASE_URL}\n"
                f"2. Search for 'Crash Listing {current_year}'\n"
                f"3. Copy doc ID from URL (`docid=XXXXX`)\n"
                f"4. Add to `cdot_manifest.json`:\n"
                f'```json\n"{current_year}": {{"doc_id": "XXXXX", "status": "preliminary", '
                f'"label": "Crash Listing {current_year} (preliminary)"}}\n```\n'
                f"5. Change {current_year - 1} status to `\"finalized\"`\n\n"
                f"Known years: {', '.join(sorted(known_years))}"
            )
    return updated


def _queue_github_issue(title: str, body: str):
    path = Path("data/CDOT/.github_issue.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"title": title, "body": body}))
    logger.info(f"  📋 GitHub issue queued: {title}")


# ═══════════════════════════════════════════════════════════════════
# XLSX → CSV
# ═══════════════════════════════════════════════════════════════════

def convert_xlsx_to_csv(xlsx_path: Path, csv_path: Path, jurisdiction: str = None) -> int:
    """Convert XLSX to CSV, optionally filtering by jurisdiction."""
    import pandas as pd

    logger.info(f"  Converting {xlsx_path.name} → {csv_path.name}")

    try:
        df = pd.read_excel(xlsx_path, sheet_name=0, engine="openpyxl")
    except Exception as e:
        logger.error(f"  Excel read failed: {e}")
        return 0

    logger.info(f"  Raw: {len(df):,} rows × {len(df.columns)} columns")

    if jurisdiction:
        mapped = JURISDICTIONS.get(jurisdiction.lower(), jurisdiction.upper())
        county_cols = [c for c in df.columns if any(
            kw in c.upper() for kw in ["COUNTY", "JURISDICTION", "CNTY"]
        )]
        if county_cols:
            col = county_cols[0]
            mask = df[col].astype(str).str.upper().str.strip().isin(
                [jurisdiction.upper(), mapped]
            )
            if mask.sum() == 0:
                mask = df[col].astype(str).str.upper().str.contains(mapped, na=False)
            df = df[mask]
            logger.info(f"  Filtered to {jurisdiction}: {len(df):,} rows")
        else:
            logger.warning(f"  No county column found, keeping all rows")

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)
    logger.info(f"  ✓ {csv_path.name}: {len(df):,} rows, {csv_path.stat().st_size:,} bytes")
    return len(df)


def file_hash(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="CDOT OnBase Crash Data Downloader")
    parser.add_argument("--data-dir", default="data/CDOT", help="Output directory for CSVs")
    parser.add_argument("--jurisdiction", default="douglas", help="County filter")
    parser.add_argument("--years", nargs="*", help="Specific years")
    parser.add_argument("--latest", action="store_true", help="Only latest preliminary year")
    parser.add_argument("--no-dict", action="store_true", help="Skip dictionary")
    parser.add_argument("--force", action="store_true", help="Re-download finalized too")
    parser.add_argument("--discover", action="store_true", help="Only run discovery")
    parser.add_argument("--headed", action="store_true", help="Show browser")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = data_dir / ".raw"
    raw_dir.mkdir(exist_ok=True)

    headless = not args.headed
    jurisdiction = args.jurisdiction.lower()

    # Load manifest
    manifest, manifest_path = load_manifest(data_dir)
    year_entries = manifest.get("years", {})

    logger.info("=" * 60)
    logger.info("CDOT Crash Data Downloader")
    logger.info(f"  Jurisdiction: {jurisdiction}")
    logger.info(f"  Known years:  {', '.join(sorted(year_entries.keys()))}")
    logger.info(f"  Manifest:     {manifest_path}")
    logger.info(f"  Output:       {data_dir.resolve()}")
    logger.info("=" * 60)

    # ── Auto-discovery (Dec/Jan/Feb/Mar or --discover) ────────────
    month = datetime.now(timezone.utc).month
    if args.discover or month in [1, 2, 3, 12]:
        if check_for_new_year(manifest, data_dir, headless):
            save_manifest(manifest, manifest_path)
            year_entries = manifest.get("years", {})

    if args.discover:
        return

    # ── DO NOT auto-finalize based on calendar year! ──────────────
    # A year only becomes "finalized" when a NEWER preliminary year
    # is added to the manifest (either via discovery or manually).
    # This ensures 2025 keeps updating monthly even in 2026.

    # ── Determine targets ─────────────────────────────────────────
    if args.years:
        targets = {y: year_entries[y] for y in args.years if y in year_entries}
    elif args.latest:
        # Find all preliminary years — these need monthly updates
        prelim = {k: v for k, v in year_entries.items() if v.get("status") == "preliminary"}
        if prelim:
            targets = prelim
        else:
            # No preliminary? Download the most recent year
            latest = max(year_entries.keys()) if year_entries else None
            targets = {latest: year_entries[latest]} if latest else {}
    else:
        targets = year_entries

    if not targets:
        logger.error("No targets! Check cdot_manifest.json.")
        sys.exit(1)

    logger.info(f"  Targets: {', '.join(sorted(targets.keys()))}")

    # ── Data dictionary ───────────────────────────────────────────
    if not args.no_dict and manifest.get("data_dictionary"):
        di = manifest["data_dictionary"]
        dict_xlsx = raw_dir / "data_dictionary.xlsx"
        dict_csv = data_dir / "data_dictionary.csv"
        if dict_csv.exists() and not args.force:
            logger.info("Dictionary exists, skipping")
        else:
            logger.info(f"Downloading dictionary (docid={di['doc_id']})...")
            if download_from_onbase(di["doc_id"], dict_xlsx, headless):
                try:
                    convert_xlsx_to_csv(dict_xlsx, dict_csv)
                except Exception as e:
                    logger.warning(f"  Dict conversion: {e}")

    # ── Download each year ────────────────────────────────────────
    results = {"downloaded": [], "skipped": [], "failed": []}

    for year in sorted(targets.keys()):
        info = targets[year]
        csv_path = data_dir / f"{year}.csv"
        xlsx_path = raw_dir / f"{year}.xlsx"
        status = info.get("status", "unknown")

        # Skip finalized unless forced
        if status == "finalized" and csv_path.exists() and not args.force:
            logger.info(f"\n{year}: Finalized, exists → skip")
            results["skipped"].append(year)
            continue

        # Preliminary: always re-download (monthly updates)
        old_hash = file_hash(csv_path)
        logger.info(f"\n{'─' * 50}")
        logger.info(f"Downloading {year} [{status}] (docid={info['doc_id']})")

        if not download_from_onbase(info["doc_id"], xlsx_path, headless):
            results["failed"].append(year)
            if status == "preliminary":
                logger.warning(f"  Will retry next run")
            continue

        # Convert XLSX → filtered CSV, saved to data/CDOT/{year}.csv
        try:
            rows = convert_xlsx_to_csv(xlsx_path, csv_path, jurisdiction)
            if rows == 0:
                logger.warning(f"  0 rows for {jurisdiction}")
                results["failed"].append(year)
                continue
        except Exception as e:
            logger.error(f"  Conversion: {e}")
            results["failed"].append(year)
            continue

        new_hash = file_hash(csv_path)
        info["last_downloaded"] = datetime.now(timezone.utc).isoformat()
        info["last_row_count"] = rows
        info["last_file_hash"] = new_hash
        info["last_file_size"] = csv_path.stat().st_size

        if new_hash != old_hash:
            results["downloaded"].append(year)
            logger.info(f"  ✓ {year} UPDATED ({csv_path.stat().st_size:,} bytes, {rows:,} rows)")
        else:
            results["skipped"].append(year)
            logger.info(f"  {year}: unchanged from last download")

    # Save manifest
    save_manifest(manifest, manifest_path)

    # Summary
    logger.info(f"\n{'=' * 60}")
    logger.info(f"Downloaded: {', '.join(results['downloaded']) or 'none'}")
    logger.info(f"Skipped:    {', '.join(results['skipped']) or 'none'}")
    logger.info(f"Failed:     {', '.join(results['failed']) or 'none'}")

    # List output files
    logger.info(f"\nFiles in {data_dir}/:")
    for f in sorted(data_dir.glob("*.csv")):
        logger.info(f"  {f.name} ({f.stat().st_size:,} bytes)")
    logger.info(f"{'=' * 60}")

    if len(results["failed"]) == len(targets) and targets:
        prelim_only = all(targets[y].get("status") == "preliminary" for y in results["failed"])
        if not prelim_only:
            sys.exit(1)


if __name__ == "__main__":
    main()
