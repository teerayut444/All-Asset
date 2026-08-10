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
    "Livinginsider": "https://www.livinginsider.com/",
    "DDproperty": "https://www.ddproperty.com/",
    "Taladnudbaan": "https://www.taladnudbaan.com/properties"
}

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
        # รัน subprocess และดึง output แสดงผลแบบ Real-time
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
                # พิมพ์ออกหน้าจอของแอปพลิเคชันหลัก
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
    parser = argparse.ArgumentParser(description="Run all asset scrapers combined.")
    parser.add_argument(
        "--pages",
        type=str,
        default="5",
        help="จำนวนหน้าที่ต้องการดึงข้อมูลสำหรับ BAM, ZmyHome, Livinginsider (ใส่ตัวเลข หรือ 'all')"
    )
    parser.add_argument(
        "--start-page",
        type=str,
        default="1",
        help="หน้าเริ่มต้นสำหรับดึงข้อมูล (ค่าเริ่มต้น: 1, BAM รองรับ 'auto')"
    )
    args = parser.parse_args()
    
    base_dir = Path(r"c:\Users\Teerayut.N\.vscode\extensions")
    
    print("\n==========================================================================")
    print(" 🔍 ตรวจสอบความพร้อมการเชื่อมต่อเว็บไซต์ปลายทาง (Website Health Check)")
    print("==========================================================================")
    
    # 1. รัน Baania Scraper
    run_scraper(
        name="Baania",
        script_name="baania_scraper.py",
        cwd=base_dir / "Baania NPA new",
        args_list=[]
    )
    
    # 2. รัน BAM Scraper
    run_scraper(
        name="BAM",
        script_name="bam_scraper.py",
        cwd=base_dir / "BAM NPA",
        args_list=["--pages", args.pages, "--start-page", "auto"]
    )
    
    # 3. รัน ZmyHome Scraper
    run_scraper(
        name="ZmyHome",
        script_name="zmyhome_scraper.py",
        cwd=base_dir / "ZmyHome NPA",
        args_list=["--pages", args.pages, "--start-page", args.start_page]
    )
    
    # 4. รัน SAM Scraper
    run_scraper(
        name="SAM",
        script_name="sam_scraper.py",
        cwd=base_dir / "SAM NPA",
        args_list=[]
    )
    
    # 5. รัน Livinginsider Scraper
    run_scraper(
        name="Livinginsider",
        script_name="livinginsider_scraper.py",
        cwd=base_dir / "Livinginsider NPA",
        args_list=["--pages", args.pages]
    )
    
    # 6. รัน DDproperty Scraper
    run_scraper(
        name="DDproperty",
        script_name="ddproperty_all_scraper.py",
        cwd=base_dir / "DDproperty NPA",
        args_list=[]
    )
    
    # 7. รัน Taladnudbaan Scraper
    run_scraper(
        name="Taladnudbaan",
        script_name="scraper.py",
        cwd=base_dir / "Taladnudbaan NPA",
        args_list=[]
    )
    
    # 8. รวมข้อมูลลง Excel
    print("\n==========================================")
    print("กำลังเริ่มรวมข้อมูลของทุกบริษัทลง Excel...")
    print("==========================================\n")
    
    try:
        # เรียกใช้ merge_excel.py
        import merge_excel
        success = merge_excel.merge_all_excel()
        if success:
            print("\n[Success] การรวมข้อมูลเสร็จสมบูรณ์เรียบร้อยแล้ว!")
        else:
            print("\n[Error] เกิดข้อผิดพลาดในการรวมข้อมูล")
    except Exception as e:
        print(f"\n[Error] ไม่สามารถรันโค้ดรวมข้อมูลได้: {e}")

if __name__ == "__main__":
    main()
