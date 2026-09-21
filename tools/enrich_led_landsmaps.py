"""
Enrich Legal Execution Department (LED) assets with exact real GPS coordinates
scraped from Department of Lands (LandsMaps: https://landsmaps.dol.go.th/).

Features:
- Single-tab browser session (no page reloading per deed).
- Automatically handles disclaimer ("รับทราบ") and not found ("ตกลง") modals.
- Incremental caching in Parquet format so work can be stopped and resumed anytime.
- Groups and sorts by Province & District to minimize dropdown switching.
"""

import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import time
import re
import glob
import argparse
from datetime import datetime
import pandas as pd
from playwright.sync_api import sync_playwright

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_SCRIPT_DIR) if os.path.basename(_SCRIPT_DIR).lower() in ["tools", "py scraper", "monthly all new"] else _SCRIPT_DIR

CACHE_PATH = os.path.join(_ROOT_DIR, "data", "led_coords_cache.parquet")
COORD_REGEX = re.compile(r'(\d{1,2}\.\d{5,})\s*,\s*(\d{2,3}\.\d{5,})')


def load_cache(cache_file=CACHE_PATH):
    """Load existing cache or create an empty DataFrame."""
    if os.path.exists(cache_file):
        try:
            return pd.read_parquet(cache_file)
        except Exception as e:
            print(f"[CACHE] Warning: Failed to read {cache_file} ({e}), starting fresh.")
    return pd.DataFrame(columns=[
        'จังหวัด', 'อำเภอ', 'เลขโฉนด', 'ละติจูด', 'ลองจิจูด', 'สถานะ', 'วันที่ดึง'
    ])


def save_cache(cache_df, cache_file=CACHE_PATH):
    """Save cache to parquet file atomically."""
    os.makedirs(os.path.dirname(os.path.abspath(cache_file)), exist_ok=True)
    temp_file = cache_file + ".tmp"
    cache_df.to_parquet(temp_file, index=False)
    if os.path.exists(cache_file):
        os.remove(cache_file)
    os.rename(temp_file, cache_file)


def find_latest_led_csv():
    """Auto-detect the most recent LED CSV output."""
    csv_files = glob.glob(os.path.join(_ROOT_DIR, "CSV_Output", "*", "LED_NPA_New_*.csv"))
    if not csv_files:
        csv_files = glob.glob(os.path.join(_ROOT_DIR, "CSV_Output", "LED_*.csv"))
    if csv_files:
        csv_files.sort(key=os.path.getmtime, reverse=True)
        return csv_files[0]
    return None


def clean_deed_number(val):
    """Standardize deed string."""
    if pd.isna(val):
        return None
    s = str(val).strip()
    if s.endswith('.0'):
        s = s[:-2]
    # Remove leading/trailing spaces or non-digit chars if it's purely a number
    s = re.sub(r'\.0$', '', s)
    s = s.strip()
    return s if s and s != '-' and s != '0' else None


def clean_district_name(val):
    """Normalize district name to match LandsMaps options."""
    if pd.isna(val):
        return ""
    d = str(val).strip()
    d = re.sub(r'^[0-9A-Za-z\u0E00-\u0E7F]+-\s*', '', d) # Remove leading codes like 01-
    d = re.sub(r'^(อ\.|อำเภอ|เขต)', '', d).strip()
    return d


def clean_province_name(val):
    """Normalize province name."""
    if pd.isna(val):
        return ""
    p = str(val).strip()
    p = re.sub(r'^(จ\.|จังหวัด)', '', p).strip()
    return p


def run_enrichment(input_file=None, cache_file=CACHE_PATH, province_filter=None, limit=None, delay=1.2, headless=False):
    # 1. Determine input file
    if not input_file:
        input_file = find_latest_led_csv()
        if not input_file:
            print("[ERROR] No LED CSV found in CSV_Output/. Please specify --input.")
            return

    print(f"=== LandsMaps Real Coordinates Scraper ===")
    print(f"Input file : {input_file}")
    print(f"Cache file : {cache_file}")
    if province_filter:
        print(f"Province   : {province_filter}")
    print("=" * 45)

    # 2. Read dataset
    if input_file.endswith('.parquet'):
        df = pd.read_parquet(input_file)
    else:
        df = pd.read_csv(input_file, low_memory=False)

    # Filter for Legal Execution Department if in merged file
    if 'บริษัท' in df.columns:
        df = df[df['บริษัท'].astype(str).str.contains('กรมบังคับคดี|LED', na=False)]

    if 'เลขโฉนด' not in df.columns or 'จังหวัด' not in df.columns or 'อำเภอ' not in df.columns:
        print("[ERROR] Input data must have 'จังหวัด', 'อำเภอ', and 'เลขโฉนด' columns.")
        return

    # Filter valid deeds
    df = df.copy()
    df['deed_clean'] = df['เลขโฉนด'].apply(clean_deed_number)
    df = df[df['deed_clean'].notna()]

    df['prov_clean'] = df['จังหวัด'].apply(clean_province_name)
    df['dist_clean'] = df['อำเภอ'].apply(clean_district_name)

    if province_filter:
        target_pv = clean_province_name(province_filter)
        df = df[df['prov_clean'].str.contains(target_pv, na=False)]

    if df.empty:
        print("[INFO] No matching records found with valid deeds.")
        return

    # 3. Load cache
    cache_df = load_cache(cache_file)
    cached_keys = set()
    if not cache_df.empty:
        for _, row in cache_df.iterrows():
            pv = clean_province_name(row.get('จังหวัด', ''))
            dt = clean_district_name(row.get('อำเภอ', ''))
            dd = clean_deed_number(row.get('เลขโฉนด', ''))
            if pv and dd:
                cached_keys.add((pv, dt, dd))

    print(f"[CACHE] Loaded {len(cache_df)} records from cache ({len(cached_keys)} unique entries).")

    # 4. Filter pending deeds
    pending_records = []
    seen = set()
    for _, row in df.iterrows():
        key = (row['prov_clean'], row['dist_clean'], row['deed_clean'])
        if key not in cached_keys and key not in seen:
            seen.add(key)
            pending_records.append({
                'จังหวัด_orig': row['จังหวัด'],
                'อำเภอ_orig': row['อำเภอ'],
                'เลขโฉนด_orig': row['เลขโฉนด'],
                'จังหวัด': row['prov_clean'],
                'อำเภอ': row['dist_clean'],
                'เลขโฉนด': row['deed_clean']
            })

    print(f"[STATUS] Total candidate deeds in file: {len(df)}")
    print(f"[STATUS] Already cached: {len(df) - len(pending_records)}")
    print(f"[STATUS] Pending search: {len(pending_records)}")

    if not pending_records:
        print("🎉 All deeds have already been processed in cache!")
        return

    if limit and limit > 0:
        pending_records = pending_records[:limit]
        print(f"[STATUS] Processing limit applied: {len(pending_records)} deeds.")

    # 5. Sort by Province & District to minimize dropdown interactions
    pending_records.sort(key=lambda x: (x['จังหวัด'], x['อำเภอ']))

    # 6. Launch Playwright session
    new_results = []
    processed_count = 0
    start_all_time = time.time()

    with sync_playwright() as p:
        print("\n[BROWSER] Launching Chrome browser...")
        try:
            browser = p.chromium.launch(channel='chrome', headless=headless)
        except Exception:
            # Fallback to default chromium
            browser = p.chromium.launch(headless=headless)

        page = browser.new_page()
        page.set_default_timeout(30000)

        print("[BROWSER] Navigating to https://landsmaps.dol.go.th/ ...")
        page.goto("https://landsmaps.dol.go.th/", wait_until="commit")

        # Dismiss initial announcement modal if present
        time.sleep(2)
        try:
            page.evaluate("""() => {
                const closeBtn = document.querySelector('button.close, [data-dismiss="modal"]');
                if (closeBtn) closeBtn.click();
                if (window.jQuery) { window.jQuery('.modal').modal('hide'); }
                document.querySelectorAll('.modal-backdrop').forEach(e => e.remove());
            }""")
        except Exception:
            pass

        # Wait for province dropdown to populate
        print("[BROWSER] Waiting for LandsMaps options to load...")
        page.wait_for_function(
            "() => { const el = document.getElementById('cbprovince'); return el && el.options && el.options.length > 10; }",
            timeout=30000
        )
        time.sleep(1)

        current_prov = None
        current_dist = None

        try:
            for idx, item in enumerate(pending_records, 1):
                prov = item['จังหวัด']
                dist = item['อำเภอ']
                deed = item['เลขโฉนด']

                print(f"\n[{idx}/{len(pending_records)}] Searching: {prov} -> {dist} -> โฉนด {deed}", flush=True)

                # Step A: Select Province if changed
                if prov != current_prov:
                    prov_res = page.evaluate(f"""(targetProv) => {{
                        const sel = document.getElementById('cbprovince');
                        for (let opt of sel.options) {{
                            if (opt.text.includes(targetProv)) {{
                                sel.value = opt.value;
                                sel.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                if (window.jQuery) {{ window.jQuery(sel).trigger('change'); }}
                                return {{ success: true, val: opt.value, text: opt.text }};
                            }}
                        }}
                        return {{ success: false }};
                    }}""", prov)

                    if not prov_res.get('success'):
                        print(f"  ❌ Province '{prov}' not found in dropdown!")
                        new_results.append({
                            'จังหวัด': item['จังหวัด_orig'],
                            'อำเภอ': item['อำเภอ_orig'],
                            'เลขโฉนด': item['เลขโฉนด_orig'],
                            'ละติจูด': None,
                            'ลองจิจูด': None,
                            'สถานะ': 'PROVINCE_NOT_FOUND',
                            'วันที่ดึง': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                        continue

                    current_prov = prov
                    current_dist = None  # Reset district when province changes
                    # Wait for district options to load
                    page.wait_for_function(
                        "() => document.querySelectorAll('#cbamphur option').length > 1",
                        timeout=15000
                    )
                    time.sleep(0.8)

                # Step B: Select District if changed
                if dist != current_dist:
                    dist_res = page.evaluate(f"""(targetDist) => {{
                        const sel = document.getElementById('cbamphur');
                        for (let opt of sel.options) {{
                            if (opt.text.includes(targetDist)) {{
                                sel.value = opt.value;
                                sel.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                if (window.jQuery) {{ window.jQuery(sel).trigger('change'); }}
                                return {{ success: true, val: opt.value, text: opt.text }};
                            }}
                        }}
                        return {{ success: false, all: Array.from(sel.options).map(o => o.text) }};
                    }}""", dist)

                    if not dist_res.get('success'):
                        print(f"  ❌ District '{dist}' not matched! Options: {dist_res.get('all', [])[:5]}...")
                        new_results.append({
                            'จังหวัด': item['จังหวัด_orig'],
                            'อำเภอ': item['อำเภอ_orig'],
                            'เลขโฉนด': item['เลขโฉนด_orig'],
                            'ละติจูด': None,
                            'ลองจิจูด': None,
                            'สถานะ': 'DISTRICT_NOT_FOUND',
                            'วันที่ดึง': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                        continue

                    current_dist = dist
                    time.sleep(0.5)

                # Step C: Input Deed Number
                page.evaluate(f"""(deedNo) => {{
                    const f1 = document.getElementById('faketxtparcelno');
                    const f2 = document.getElementById('txtparcelno');
                    if (f1) {{
                        f1.value = deedNo;
                        f1.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        f1.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                    if (f2) {{
                        f2.value = deedNo;
                        f2.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        f2.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                }}""", deed)
                time.sleep(0.3)

                # Step D: Clear previous results DOM before starting new search
                page.evaluate("""() => {
                    if (typeof clearInfo === 'function') { clearInfo(); }
                    const oldCards = document.querySelectorAll('#infotext, .modal-info, [id*="info"]');
                    oldCards.forEach(e => {
                        if (e.innerText.includes('ค่าพิกัดแปลง') || e.innerText.includes('ข้อมูลแปลงที่ดิน')) {
                            e.remove();
                        }
                    });
                }""")
                time.sleep(0.2)

                # Step E: Trigger Search
                page.evaluate("""() => {
                    if (typeof searchByParcelNo === 'function') {
                        searchByParcelNo();
                    } else {
                        const b = document.getElementById('btnSearch');
                        if (b) b.click();
                    }
                }""")

                # Step E: Wait for result (FOUND or NOT_FOUND)
                status = 'TIMEOUT'
                lat_found = None
                lon_found = None
                t0 = time.time()

                while time.time() - t0 < 12:
                    time.sleep(0.6)

                    # 1. Click "รับทราบ" if disclaimer modal appears
                    page.evaluate("""() => {
                        const btns = Array.from(document.querySelectorAll('button, a')).filter(b => b.innerText.trim() === 'รับทราบ');
                        if (btns.length > 0) {
                            btns[btns.length - 1].click();
                        }
                    }""")

                    # 2. Check for coordinates
                    check = page.evaluate("""() => {
                        const body = document.body.innerText;
                        const match = body.match(/(\\d{1,2}\\.\\d{5,})\\s*,\\s*(\\d{2,3}\\.\\d{5,})/);
                        let linkMatch = null;
                        const els = Array.from(document.querySelectorAll('a, span, td, div'));
                        for (let el of els) {
                            const m = el.innerText.match(/(\\d{1,2}\\.\\d{5,})\\s*,\\s*(\\d{2,3}\\.\\d{5,})/);
                            if (m) {
                                linkMatch = [m[1], m[2]];
                                break;
                            }
                        }
                        const notFoundModal = Array.from(document.querySelectorAll('.modal, .sweet-alert, div[role="dialog"]'))
                            .some(m => m.offsetParent !== null && m.innerText.includes('ไม่พบข้อมูล'));
                        return {
                            coords: linkMatch || (match ? [match[1], match[2]] : null),
                            notFound: notFoundModal
                        };
                    }""")

                    if check.get('coords'):
                        lat_found = float(check['coords'][0])
                        lon_found = float(check['coords'][1])
                        status = 'FOUND'
                        print(f"  🎯 [FOUND] Real GPS: Lat={lat_found:.8f}, Lon={lon_found:.8f}", flush=True)

                        # Dismiss the parcel info card to clean DOM for next search
                        page.evaluate("""() => {
                            const btn = Array.from(document.querySelectorAll('button, a')).find(b => b.innerText.includes('ปิดหน้าต่าง'));
                            if (btn) btn.click();
                        }""")
                        break

                    if check.get('notFound'):
                        status = 'NOT_FOUND'
                        print("  ❌ [NOT FOUND] Dismissed modal.", flush=True)
                        # Click 'ตกลง' to dismiss
                        page.evaluate("""() => {
                            const btns = Array.from(document.querySelectorAll('button, a')).filter(b => b.innerText.trim() === 'ตกลง');
                            if (btns.length > 0) {
                                btns[btns.length - 1].click();
                            }
                            if (window.jQuery) { window.jQuery('.modal').modal('hide'); }
                            document.querySelectorAll('.modal-backdrop').forEach(e => e.remove());
                        }""")
                        break

                if status == 'TIMEOUT':
                    print("  ⚠️ [TIMEOUT] No response within 12 seconds.")

                new_results.append({
                    'จังหวัด': item['จังหวัด_orig'],
                    'อำเภอ': item['อำเภอ_orig'],
                    'เลขโฉนด': item['เลขโฉนด_orig'],
                    'ละติจูด': lat_found,
                    'ลองจิจูด': lon_found,
                    'สถานะ': status,
                    'วันที่ดึง': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })

                processed_count += 1

                # Periodically save cache every 10 deeds
                if len(new_results) >= 10:
                    batch_df = pd.DataFrame(new_results)
                    cache_df = pd.concat([cache_df, batch_df], ignore_index=True)
                    save_cache(cache_df, cache_file)
                    new_results.clear()
                    print(f"  [SAVED] Progress saved to {cache_file} (Total in cache: {len(cache_df)})")

                time.sleep(delay)

        except KeyboardInterrupt:
            print("\n[INTERRUPTED] User cancelled process. Saving current progress...")
        finally:
            # Save any remaining results
            if new_results:
                batch_df = pd.DataFrame(new_results)
                cache_df = pd.concat([cache_df, batch_df], ignore_index=True)
                save_cache(cache_df, cache_file)
                print(f"[SAVED] Final progress saved to {cache_file} (Total in cache: {len(cache_df)})")

            browser.close()

    elapsed = time.time() - start_all_time
    print("\n" + "=" * 45)
    print(f"🎉 Completed! Processed {processed_count} deeds in {elapsed:.1f} seconds.")
    if not cache_df.empty:
        found_cnt = (cache_df['สถานะ'] == 'FOUND').sum()
        not_found_cnt = (cache_df['สถานะ'] == 'NOT_FOUND').sum()
        print(f"Cache summary:")
        print(f" - FOUND real GPS: {found_cnt} assets")
        print(f" - NOT FOUND     : {not_found_cnt} assets")
        print(f" - Total in cache: {len(cache_df)}")
    print("=" * 45)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Scrape real coordinates from LandsMaps for LED assets")
    parser.add_argument('--input', type=str, help="Input CSV or Parquet file path")
    parser.add_argument('--cache', type=str, default=CACHE_PATH, help="Cache Parquet file path")
    parser.add_argument('--province', type=str, help="Filter search to specific province")
    parser.add_argument('--limit', type=int, default=0, help="Limit number of deeds to process (0 = all)")
    parser.add_argument('--delay', type=float, default=1.2, help="Delay between searches in seconds")
    parser.add_argument('--headless', action='store_true', help="Run browser in headless mode")

    args = parser.parse_args()
    run_enrichment(
        input_file=args.input,
        cache_file=args.cache,
        province_filter=args.province,
        limit=args.limit,
        delay=args.delay,
        headless=args.headless
    )
