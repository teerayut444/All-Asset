import subprocess
import sys
import argparse
from pathlib import Path

def run_scraper(name: str, script_name: str, cwd: Path, args_list: list) -> bool:
    print(f"\n==========================================")
    print(f"กำลังเริ่มรันระบบดึงข้อมูล: {name}")
    print(f"Directory: {cwd}")
    print(f"Command: python {script_name} {' '.join(args_list)}")
    print(f"==========================================\n")
    
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
    parser = argparse.ArgumentParser(description="Run Baania, BAM, and ZmyHome scrapers combined.")
    parser.add_argument(
        "--pages",
        type=str,
        default="5",
        help="จำนวนหน้าที่ต้องการดึงข้อมูลสำหรับ BAM และ ZmyHome (ใส่ตัวเลข หรือ 'all')"
    )
    parser.add_argument(
        "--start-page",
        type=str,
        default="1",
        help="หน้าเริ่มต้นสำหรับดึงข้อมูล (ค่าเริ่มต้น: 1, BAM รองรับ 'auto')"
    )
    args = parser.parse_args()
    
    base_dir = Path(r"c:\Users\Teerayut.N\.vscode\extensions")
    
    # 1. รัน Baania Scraper
    # Baania NPA Scraper ไม่จำเป็นต้องระบุหน้าเพราะดึงจนถึงวันที่ Cutoff โดยอัตโนมัติ
    run_scraper(
        name="Baania",
        script_name="baania_scraper.py",
        cwd=base_dir / "Baania NPA",
        args_list=[]
    )
    
    # 2. รัน BAM Scraper
    run_scraper(
        name="BAM",
        script_name="bam_scraper.py",
        cwd=base_dir / "BAM NPA",
        # ส่งต่อหน้าและเริ่มแบบ auto เสมอเพื่อให้ต่อเนื่อง
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
    
    # 5. รวมข้อมูลลง Excel
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
