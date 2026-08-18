import subprocess
import sys
import os
import time
import threading
import collections
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.system('') # Enable ANSI escape codes in Windows Console

SCRAPERS = [
    {"name": "Baania", "script": "scrape_baania_monthly.py"},
    {"name": "BAM", "script": "scrape_bam_monthly.py"},
    {"name": "ZmyHome", "script": "scrape_zmyhome_monthly.py"},
    {"name": "SAM", "script": "scrape_sam_monthly.py"},
    {"name": "DDproperty", "script": "scrape_ddproperty_monthly.py"},
    {"name": "Taladnudbaan", "script": "scrape_taladnudbaan_monthly.py"},
    {"name": "Chayo555", "script": "scrape_chayo555_monthly.py"},
    {"name": "NaYoo", "script": "scrape_nayoo_monthly.py"}
]

status_dict = {s["name"]: f"[{s['name']:<13s}] [░░░░░░░░░░░░░░░░░░░░]   0% | (    0/    0 หน้า) | สะสม:       0 รายการ | กำลังเริ่มต้น..." for s in SCRAPERS}
company_health = {s["name"]: "🌐 ตรวจสอบสถานะลิงก์ปลายทาง..." for s in SCRAPERS}
recent_logs = collections.deque(maxlen=7)

lock = threading.Lock()
running = True

def add_log(msg):
    time_str = datetime.now().strftime("%H:%M:%S")
    recent_logs.appendleft(f"[{time_str}] {msg}")

BORDER_LINE = "=" * 120

def draw_fixed_dashboard():
    with lock:
        # Move cursor to top-left home position
        sys.stdout.write("\033[H")
        sys.stdout.write(f"{BORDER_LINE}\n")
        sys.stdout.write("🚀 Live Dashboard: Scraper Monthly ขนาน 8 บริษัท (Fixed Screen Aligned Mode)\n")
        sys.stdout.write(f"{BORDER_LINE}\n")
        for s in SCRAPERS:
            name = s["name"]
            st_line = status_dict[name]
            h_line = company_health[name]
            sys.stdout.write(f"\033[K{st_line}\n")
            sys.stdout.write(f"\033[K └─ {h_line}\n")
        sys.stdout.write(f"{BORDER_LINE}\n")
        sys.stdout.write("📜 บันทึกแจ้งเตือนล่าสุด (7 บรรทัดล่าสุด):\n")
        logs_list = list(recent_logs)
        for i in range(7):
            if i < len(logs_list):
                sys.stdout.write(f"\033[K {logs_list[i]}\n")
            else:
                sys.stdout.write("\033[K -\n")
        sys.stdout.write(f"{BORDER_LINE}\n")
        sys.stdout.flush()

def ui_refresh_loop():
    while running:
        draw_fixed_dashboard()
        time.sleep(0.25)

def stream_process_output(process, name):
    buffer = ""
    while True:
        char = process.stdout.read(1)
        if not char:
            break
        if char == '\r' or char == '\n':
            line = buffer.strip()
            buffer = ""
            if line:
                # Ignore divider lines like ====================
                if set(line) <= {"=", "-", "*", "#"}:
                    continue
                    
                if "สถานะลิงก์" in line:
                    clean_msg = line.replace(f"[{name}]", "").strip()
                    with lock:
                        company_health[name] = clean_msg
                        add_log(f"[{name}] {clean_msg}")
                elif "สแครปเสร็จสมบูรณ์" in line or "เสร็จสมบูรณ์" in line or "ครบถ้วน 100%" in line or "สิ้นสุดการสแครป" in line:
                    clean_msg = line.replace(f"[{name}]", "").replace("✅", "").replace("🎉", "").strip()
                    completed_line = f"[{name:<13s}] [████████████████████] 100% | ✅ {clean_msg}"
                    with lock:
                        status_dict[name] = completed_line
                        add_log(f"[{name}] ✅ {clean_msg}")
                elif "Milestone" in line or "ALERT" in line or "Smart Resume" in line or "Fast-Forward" in line:
                    clean_msg = line.replace(f"[{name}]", "").strip()
                    with lock:
                        add_log(f"[{name}] {clean_msg}")
                elif line.startswith(f"[{name}") or line.startswith(f"[{name:<13s}]"):
                    if "✅" not in status_dict[name]:
                        with lock:
                            status_dict[name] = line
                elif ("%" in line or "สะสม" in line or "รายการ" in line) and "✅" not in status_dict[name]:
                    with lock:
                        status_dict[name] = f"[{name:<13s}] {line}"
        else:
            buffer += char

def main():
    global running
    base_dir = Path(__file__).parent.resolve()
    python_exe = sys.executable
    
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    
    # Clear screen once at startup
    os.system('cls' if os.name == 'nt' else 'clear')
    
    with lock:
        add_log("เริ่มต้นระบบ Scraper Monthly แบบขนาน 6 บริษัท")
    
    ui_thread = threading.Thread(target=ui_refresh_loop)
    ui_thread.daemon = True
    ui_thread.start()
    
    processes = []
    start_time = time.time()
    
    is_frozen = getattr(sys, 'frozen', False)
    
    for scraper in SCRAPERS:
        name = scraper["name"]
        script_file = base_dir / scraper["script"]
        
        if is_frozen:
            cmd = [sys.executable, "--worker", name]
        else:
            if not script_file.exists():
                with lock:
                    status_dict[name] = f"[{name:<13s}] ❌ ไม่พบไฟล์สคริปต์"
                    company_health[name] = "❌ ไม่พบไฟล์สคริปต์"
                    add_log(f"[{name}] ❌ ไม่พบไฟล์สคริปต์")
                continue
            cmd = [python_exe, "-u", str(script_file)]
        
        try:
            p = subprocess.Popen(
                cmd,
                cwd=base_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env
            )
            processes.append((name, p))
        except Exception as e:
            with lock:
                status_dict[name] = f"[{name:<13s}] ❌ สั่งรันไม่ได้: {e}"
                company_health[name] = f"❌ สั่งรันไม่ได้: {e}"
                add_log(f"[{name}] ❌ สั่งรันไม่ได้: {e}")
            
    threads = []
    for name, p in processes:
        t = threading.Thread(target=stream_process_output, args=(p, name))
        t.daemon = True
        t.start()
        threads.append(t)
        
    for name, p in processes:
        p.wait()
        if p.returncode == 0 and "✅" not in status_dict[name]:
            with lock:
                status_dict[name] = f"[{name:<13s}] [████████████████████] 100% | ✅ สแครปเสร็จสมบูรณ์เรียบร้อยแล้ว!"
        
    for t in threads:
        t.join(timeout=2)
        
    running = False
    time.sleep(0.4)
    
    with lock:
        add_log("ทั้ง 8 บริษัท สแครปเสร็จสมบูรณ์แล้ว!")
        
    draw_fixed_dashboard()
    
    elapsed = time.time() - start_time

    print("\n" + BORDER_LINE, flush=True)
    print("🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔", flush=True)
    print("🎉🎉🎉 [FINISHED] ทั้ง 8 บริษัท สแครปและรวมไฟล์เสร็จสมบูรณ์ 100% เรียบร้อยแล้ว! 🎉🎉🎉", flush=True)
    print("🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔", flush=True)
    print(f"⏱️ รวมเวลาที่ใช้ในการรันขนานทั้งหมด: {elapsed/60:.2f} นาที", flush=True)
    print(BORDER_LINE, flush=True)
    
    try:
        import merge_csv_monthly
        merge_csv_monthly.merge_monthly_csv()
        print("\n✅ [SUCCESS] รวมไฟล์และอัปเดต all_assets.parquet เรียบร้อย พร้อมใช้งานบน Dashboard!", flush=True)
    except Exception as e:
        print(f"⚠️ เกิดข้อผิดพลาดในการรวมไฟล์: {e}", flush=True)

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--worker":
        worker = sys.argv[2]
        if worker == "Baania":
            import scrape_baania_monthly; scrape_baania_monthly.main()
        elif worker == "BAM":
            import scrape_bam_monthly; scrape_bam_monthly.main()
        elif worker == "ZmyHome":
            import scrape_zmyhome_monthly; scrape_zmyhome_monthly.main()
        elif worker == "SAM":
            import scrape_sam_monthly; scrape_sam_monthly.main()
        elif worker == "DDproperty":
            import scrape_ddproperty_monthly; scrape_ddproperty_monthly.main()
        elif worker == "Taladnudbaan":
            import scrape_taladnudbaan_monthly; scrape_taladnudbaan_monthly.main()
        elif worker == "Chayo555":
            import scrape_chayo555_monthly; scrape_chayo555_monthly.main()
        elif worker == "NaYoo":
            import scrape_nayoo_monthly; scrape_nayoo_monthly.main()
        sys.exit(0)
    else:
        main()
