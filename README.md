# 🏢 All Asset NPA Intelligence Dashboard (12 Sources)

ระบบแดชบอร์ดวิเคราะห์และเปรียบเทียบข้อมูลทรัพย์สินรอการขาย (NPA) ครบวงจร ครอบคลุมสถาบันการเงินและแพลตฟอร์มอสังหาริมทรัพย์ชั้นนำกว่า 12 แหล่งในประเทศไทย (SAM, BAM, KBANK, SCB, KTB, GHB, GSB, Chayo555, NaYoo, Baania, ZmyHome, Taladnudbaan) พร้อมระบบแผนที่ Interactive พิกัดจริง และการประเมินราคากลางเชิงลึก

---

## ⚡ วิธีรันด่วน (Quick Start สำหรับเครื่องใหม่)

> [!TIP]
> สำหรับเครื่องที่ยังไม่เคยติดตั้ง Environment เพียงแค่ดับเบิ้ลคลิกไฟล์เดียว ระบบจะจัดการสร้าง `.venv` ติดตั้ง Library และเปิด Dashboard ให้อัตโนมัติ!

1. ตรวจสอบว่าเครื่องมี **Python 3.10 ขึ้นไป** ([ดาวน์โหลด Python](https://www.python.org/downloads/))
   - ⚠️ **สำคัญมาก:** ตอนติดตั้ง Python ให้ติ๊กถูกที่ช่อง **`Add Python to PATH`** หรือ `Add python.exe to PATH`
2. ดับเบิ้ลคลิกที่ไฟล์ **`start_dashboard.bat`**
3. ระบบจะเปิดหน้าเว็บ Dashboard บนเบราว์เซอร์ที่ URL: `http://localhost:8501`

---

## 📁 โครงสร้างโปรเจกต์ (Project Structure)

```text
📁 All Asset Dashboard/
│
├── 🚀 run_dashboard.bat               # รัน Dashboard หลัก (Modular Version - เร็วและเสถียร)
├── 🚀 run_legacy_backup.bat           # รัน Dashboard สำรองเวอร์ชันเดิม (Monolithic Backup)
├── ⚙️ Scraper_Monthly_Parallel.exe     # โปรแกรมดึงข้อมูลรายเดือน 14 สถาบัน (EXE)
├── 🔨 build_scraper_exe.bat           # สคริปต์คอมไพล์ Scraper เป็น EXE
│
├── 📄 all_assets.parquet              # ฐานข้อมูลหลักของทรัพย์สิน NPA (~200,000+ รายการ)
├── 📄 requirements.txt                # รายการ Python Libraries ที่จำเป็น
├── 📄 README.md                       # เอกสารคู่มือการติดตั้งและใช้งาน
│
├── 🐍 app.py                          # แอปพลิเคชันหลัก Modular Entrypoint (~110 บรรทัด)
├── 🐍 app_legacy_monolithic.py        # โค้ดสำรองเวอร์ชันเดิม Monolithic Backup (~8,760 บรรทัด)
├── 🐍 sam_analytics.py                # โมดูลวิเคราะห์โครงการเดียวกัน & สถิติเชิงลึก
├── 🐍 bubble_chart.py                 # โมดูล 3D Glossy Bubble Chart
│
├── 📁 modules/                        # โครงสร้างโมดูลหลัก (config, services, ui, views)
├── 📁 packaging/                      # แหล่งรวมสคริปต์บิลด์และ Deploy Package
├── 📁 Py Scraper/                     # สคริปต์ดึงข้อมูล 14 สถาบันและตัวรวมข้อมูล
├── 📁 QA_Checker/                     # เครื่องมือตรวจสอบคุณภาพข้อมูล
├── 📁 tools/                          # สคริปต์เสริมและเครื่องมือวิเคราะห์
├── 📁 data/                           # ฐานข้อมูลพิกัดและ GeoJSON ขอบเขต
├── 📁 logo/ & static/ & assets/       # โลโก้และสไตล์แผนที่
└── 📁 backups/                        # คลังสำรองโค้ดเวอร์ชันเดิมทั้งหมด
```

---

## 💻 วิธีการรันผ่าน Terminal / Command Line (Manual)

หากต้องการติดตั้งและรันผ่าน Command Line / Terminal:

1. **สร้าง Python Virtual Environment:**
   ```bash
   python -m venv .venv
   ```

2. **เปิดใช้งาน Environment:**
   - **Windows (Command Prompt / PowerShell):**
     ```cmd
     .venv\Scripts\activate
     ```
   - **macOS / Linux:**
     ```bash
     source .venv/bin/activate
     ```

3. **ติดตั้ง Dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **เริ่มรัน Dashboard:**
   ```bash
   streamlit run app.py
   ```

---

## 🌐 การนำไป Host บน Server ภายในองค์กร (Local Network / LAN)

หากต้องการรันบนเครื่อง Server หรือคอมพิวเตอร์เครื่องหนึ่งเพื่อให้คนอื่นในเครือข่ายเข้าใช้งานได้:

```cmd
streamlit run app.py --server.port=8501 --server.address=0.0.0.0 --server.maxUploadSize=500
```

- เข้าใช้งานจากเครื่องอื่นในวง LAN: `http://<IP_เครื่อง_SERVER>:8501`

---

## 📊 ฟังก์ชันหลักของระบบ (Core Features)

1. 🔮 **ภาพรวม & แผนที่ (Bubble & Map)**:
   - 3D Glossy Bubble Chart แสดงสัดส่วนพอร์ตโฟลิโอตามภูมิภาค/ประเภททรัพย์
   - แผนที่ความหนาแน่นและพิกัดจริงทั่วประเทศ
2. 📈 **สถิติ & วิเคราะห์ (Analytics)**:
   - วิเคราะห์ราคาเฉลี่ยต่อตารางวา/ตารางเมตร เปรียบเทียบระหว่างสถาบันการเงิน
   - กราฟแจกแจงช่วงราคาและส่วนลด
3. 🔍 **เปรียบเทียบตำแหน่ง & โครงการ (Comparison)**:
   - 📍 *ค้นหาตามรัศมีทำเล*: เปรียบเทียบทรัพย์รอบจุดอ้างอิง
   - 🏘️ *เปรียบเทียบในโครงการเดียวกัน*: เจาะลึกทรัพย์ทุกยูนิตในโครงการเดียวกัน พร้อมแผนที่ Logo Pin
4. 📋 **รายการทรัพย์สิน (Property Listing)**:
   - ระบบค้นหาและตัวกรองละเอียดระดับตำบล อำเภอ จังหวัด
   - ส่งออกข้อมูลเป็น Excel (.xlsx) และ CSV
