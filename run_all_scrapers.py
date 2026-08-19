import subprocess
import sys
import argparse
import time
from pathlib import Path
import requests
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Reconfigure stdout to UTF-8 to prevent encoding crashes on Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

TARGET_URLS = {
    "Baania": "https://www.baania.com/s/%E0%B8%97%E0%B8%B1%E0%B9%89%E0%B8%87%E0%B8%AB%E0%B8%A1%E0%B8%94/listing",
    "BAM": "https://www.bam.co.th/th/npa/property/search",
    "ZmyHome": "https://zmyhome.com/buy",
    "SAM": "https://sam.or.th/site/npa/page_list.php",
    "Taladnudbaan": "https://www.taladnudbaan.com/properties",
    "Chayo555": "https://www.chayo555.com/property",
    "NaYoo": "https://nayoo.co/"
}

SCRAPERS = [
    {"name": "Baania", "script": "scrape_baania_monthly.py"},
    {"name": "BAM", "script": "scrape_bam_monthly.py"},
    {"name": "ZmyHome", "script": "scrape_zmyhome_monthly.py"},
    {"name": "SAM", "script": "scrape_sam_monthly.py"},
    {"name": "Taladnudbaan", "script": "scrape_taladnudbaan_monthly.py"},
    {"name": "Chayo555", "script": "scrape_chayo555_monthly.py"},
    {"name": "NaYoo", "script": "scrape_nayoo_monthly.py"}
]

def check_website_accessibility(name: str, url: str) -> bool:
    """ตรวจสอบว่าเว็บปลายทางสามารถเชื่อมต่อและตอบสนองได้ตามปกติหรือไม่"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    t0 = time.time()
    try:
        r = requests.get(url, headers=headers, timeout=12, verify=False)
        elapsed = time.time() - t0
        if r.status_code in [200, 301, 302, 307, 308]:
            print(f"[Health Check] 🟢 {name} ({url}) | สถานะ: ONLINE (HTTP {r.status_code}) | ตอบสนองใน {elapsed:.2f} วินาที")
            return True
        else:
            print(f"[Health Check] ⚠️ {name} ({url}) | สถานะ: HTTP Error {r.status_code} | เวลา: {elapsed:.2f} วินาที")
            return False
    except Exception as e:
        elapsed = time.time() - t0
        print(f"[Health Check] ❌ {name} ({url}) | ไม่สามารถเข้าถึงได้ ({e}) | เวลา: {elapsed:.2f} วินาที")
        return False

def run_scraper(name: str, script_name: str, cwd: Path, args_list: list, target_url: str = None) -> bool:
    print(f"\n==========================================")
    print(f"กำลังเริ่มรันระบบดึงข้อมูล: {name}")
    print(f"Directory: {cwd}")
    print(f"Command: python {script_name} {' '.join(args_list)}")
    print(f"==========================================")
    
    # 1. Pre-flight health check
    url = target_url or TARGET_URLS.get(name)
    if url:
        is_online = check_website_accessibility(name, url)
        if not is_online:
            print(f"\n[Skip Warning] ⚠️ ข้ามการรันระบบดึงข้อมูลของ {name} เนื่องจากเซิร์ฟเวอร์เว็บปลายทางไม่ตอบสนองหรือขัดข้องชั่วคราว\n")
            return False
    
    python_exe = sys.executable
    cmd = [python_exe, script_name] + args_list
    
    try:
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                sys.stdout.write(output)
                sys.stdout.flush()
                
        rc = process.poll()
        if rc == 0:
            print(f"\n[Success] ดึงข้อมูลของ {name} สำเร็จเรียบร้อย!")
            return True
        else:
            print(f"\n[Warning] ระบบขูดของ {name} จบการทำงานด้วยรหัสข้อผิดพลาด: {rc}")
            return False
            
    except Exception as e:
        print(f"\n[Error] ไม่สามารถรัน Scraper ของ {name} ได้: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Run all asset scrapers from Monthly all new.")
    parser.add_argument("--parallel", action="store_true", help="รันแบบขนานพร้อมกันทุกบริษัท (Fast Mode)")
    args = parser.parse_args()
    
    root_dir = Path(__file__).parent.resolve()
    monthly_dir = root_dir / "Monthly all new"
    
    if args.parallel:
        print("🚀 รันระบบดึงข้อมูลแบบขนานผ่าน run_parallel_monthly.py...")
        p_script = monthly_dir / "run_parallel_monthly.py"
        subprocess.run([sys.executable, str(p_script)], cwd=monthly_dir)
        return

    print("\n==========================================================================")
    print(" 🔍 ตรวจสอบความพร้อมการเชื่อมต่อเว็บไซต์ปลายทาง (Website Health Check)")
    print(" 📂 อ้างอิงโฟลเดอร์หลัก: Monthly all new")
    print("==========================================================================")
    
    for s in SCRAPERS:
        run_scraper(
            name=s["name"],
            script_name=s["script"],
            cwd=monthly_dir,
            args_list=[]
        )
    
    # รวมข้อมูลเป็น all_assets_monthly_YYYY_MM.csv และแปลงเฉพาะไฟล์นี้เป็น all_assets.parquet
    print("\n==========================================")
    print("กำลังเริ่มรวมข้อมูล CSV และแปลงเป็น all_assets.parquet...")
    print("==========================================\n")
    
    try:
        sys.path.insert(0, str(monthly_dir))
        import merge_csv_monthly
        merge_csv_monthly.merge_monthly_csv()
    except Exception as e:
        print(f"\n[Error] เกิดข้อผิดพลาดในการรวมและแปลงข้อมูล: {e}")

if __name__ == "__main__":
    main()
