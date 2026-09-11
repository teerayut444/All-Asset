# -*- coding: utf-8 -*-
"""
Standalone in-process Streamlit runner for standalone PyInstaller packaging.
"""
import sys
import os
import streamlit.web.bootstrap as bootstrap
import webbrowser
import threading
import time

# Ensure UTF-8
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

def get_bundle_dir():
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', get_base_dir())
    return get_base_dir()

def main():
    base_dir = get_base_dir()
    bundle_dir = get_bundle_dir()
    
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
    if bundle_dir not in sys.path:
        sys.path.insert(0, bundle_dir)
        
    # Locate app.py (either in folder next to exe, or bundled inside MEIPASS)
    app_file = os.path.join(base_dir, "app.py")
    if not os.path.exists(app_file):
        app_file = os.path.join(bundle_dir, "app.py")
        
    os.chdir(base_dir)

    print("=" * 70)
    print("  🏢 ALL ASSET NPA INTELLIGENCE DASHBOARD (PORTABLE STANDALONE)")
    print("  พร้อมใช้งานบนทุกเครื่อง Windows ทันทีโดยไม่ต้องลง Python")
    print("=" * 70)
    print(f"📁 Directory: {base_dir}")
    print(f"🌐 Server:    http://localhost:8501")
    print("-" * 70)
    print("🚀 กำลังเริ่มต้นระบบ Dashboard และเปิดหน้าต่างเบราว์เซอร์อัตโนมัติ...\n")

    def open_browser():
        time.sleep(2.5)
        webbrowser.open("http://localhost:8501")

    threading.Thread(target=open_browser, daemon=True).start()

    # Run Streamlit in-process
    flag_options = {
        "server.port": 8501,
        "server.maxUploadSize": 500,
        "server.headless": False,
        "server.enableCORS": False,
        "server.enableXsrfProtection": False,
        "browser.gatherUsageStats": False,
        "global.developmentMode": False
    }

    bootstrap.load_config_options(flag_options=flag_options)
    bootstrap.run(app_file, False, [], flag_options=flag_options)

if __name__ == "__main__":
    main()
