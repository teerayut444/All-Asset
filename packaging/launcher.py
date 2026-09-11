# -*- coding: utf-8 -*-
"""
All Asset Dashboard - Windows EXE Launcher
Launches Streamlit Dashboard automatically with browser auto-open and environment auto-detection.
"""
import sys
import os
import subprocess
import webbrowser
import time
import threading
import shutil

# Ensure UTF-8 output on Windows console
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

def find_python(base_dir):
    # 1. Local virtual environment
    venv_py = os.path.join(base_dir, ".venv", "Scripts", "python.exe")
    if os.path.exists(venv_py):
        return venv_py
        
    # 2. Virtual environment in parent
    parent_venv = os.path.join(base_dir, "..", ".venv", "Scripts", "python.exe")
    if os.path.exists(parent_venv):
        return parent_venv
        
    # 3. System PATH Python
    for name in ["python", "py", "python3"]:
        path = shutil.which(name)
        if path:
            return path
            
    return sys.executable

# Enable Virtual Terminal Processing & Clean Console Setup on Windows
if sys.platform == 'win32':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        h_out = kernel32.GetStdHandle(-11) # STD_OUTPUT_HANDLE
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(h_out, ctypes.byref(mode))
        mode.value |= 0x0004 # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        kernel32.SetConsoleMode(h_out, mode)
        kernel32.SetConsoleTitleW("All Asset NPA Intelligence Dashboard")
    except Exception:
        pass

COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_GRAY = "\033[90m"

def main():
    base_dir = get_base_dir()
    os.chdir(base_dir)
    
    CARD_W = 76
    print("\n" + "┌" + "─" * (CARD_W - 2) + "┐")
    print(f"│  {COLOR_CYAN}{COLOR_BOLD}[APP] ALL ASSET NPA INTELLIGENCE DASHBOARD{COLOR_RESET}" + " " * (CARD_W - 44) + "│")
    print(f"│  {COLOR_GRAY}ระบบวิเคราะห์และเปรียบเทียบข้อมูลทรัพย์ NPA 14 สถาบันชั้นนำทั่วประเทศ{COLOR_RESET}" + " " * 4 + "│")
    print("└" + "─" * (CARD_W - 2) + "┘")
    
    app_file = os.path.join(base_dir, "app.py")
    if not os.path.exists(app_file):
        parent_app = os.path.join(base_dir, "..", "app.py")
        if os.path.exists(parent_app):
            base_dir = os.path.abspath(os.path.join(base_dir, ".."))
            os.chdir(base_dir)
            app_file = os.path.join(base_dir, "app.py")

    if not os.path.exists(app_file):
        print(f"\n{COLOR_YELLOW}[ERROR] ไม่พบไฟล์ app.py ในโฟลเดอร์: {base_dir}{COLOR_RESET}")
        print("กรุณาวางไฟล์ All_Asset_Dashboard.exe ไว้ในโฟลเดอร์เดียวกันกับ app.py")
        input("\nกด Enter เพื่อปิดหน้าต่าง...")
        return

    python_exe = find_python(base_dir)
    print(f"\n [DIR] {COLOR_BOLD}Project Root :{COLOR_RESET} {base_dir}")
    print(f" [ENV] {COLOR_BOLD}Python Engine:{COLOR_RESET} {python_exe}")
    print(f" [URL] {COLOR_BOLD}Local Server :{COLOR_RESET} {COLOR_GREEN}http://localhost:8501{COLOR_RESET}")
    print(" " + "─" * (CARD_W - 2))
    print(f" [INIT] {COLOR_CYAN}{COLOR_BOLD}กำลังเริ่มต้นระบบ Streamlit Server และเปิดเบราว์เซอร์อัตโนมัติ...{COLOR_RESET}")
    print(f" {COLOR_GRAY}[TIP] เมื่อใช้งานเสร็จแล้ว สามารถกด Ctrl+C หรือปิดหน้าต่างนี้เพื่อปิดระบบ{COLOR_RESET}\n")

    # Thread to auto open web browser
    def open_browser():
        time.sleep(2.2)
        webbrowser.open("http://localhost:8501")

    t = threading.Thread(target=open_browser, daemon=True)
    t.start()

    cmd = [
        python_exe, "-m", "streamlit", "run", "app.py",
        "--server.port=8501",
        "--server.maxUploadSize=500",
        "--browser.gatherUsageStats=false"
    ]

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print(f"\n\n{COLOR_GREEN}[SHUTDOWN] ปิดระบบ All Asset Dashboard เรียบร้อยแล้ว{COLOR_RESET}")
    except Exception as e:
        print(f"\n[ERROR]: {e}")
        input("\nกด Enter เพื่อปิดหน้าต่าง...")

if __name__ == "__main__":
    main()
