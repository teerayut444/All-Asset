# NOVA NPA Intelligence Dashboard (14 Sources)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40%2B-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Storage](https://img.shields.io/badge/Data-Apache%20Parquet-008080?logo=apache&logoColor=white)](https://parquet.apache.org/)
[![GIS](https://img.shields.io/badge/GIS-Deck.gl%20%7C%20Shapely-3B82F6)](https://deck.gl/)
[![Coverage](https://img.shields.io/badge/Sources-14%20Platforms-success)](#สถาบันและแพลตฟอร์มที่ครอบคลุม-14-sources)

ระบบแดชบอร์ดวิเคราะห์และเปรียบเทียบข้อมูลทรัพย์สินรอการขาย (NPA) อัจฉริยะแบบครบวงจร รวบรวมข้อมูลจากสถาบันการเงิน กรมบังคับคดี และแพลตฟอร์มอสังหาริมทรัพย์ชั้นนำกว่า **14 แหล่งทั่วประเทศไทย** พร้อมระบบแผนที่ Interactive พิกัดจริง (GPU-Accelerated), การวิเคราะห์เปรียบเทียบราคากลาง, และระบบคัดกรองทรัพย์เชิงลึก

---

### สถาบันและแพลตฟอร์มที่ครอบคลุม (14 Sources)

- **สถาบันการเงินและ AMC รัฐ/เอกชน**: SAM (บสส.), BAM, LED (กรมบังคับคดี), GHB (ธนาคารอาคารสงเคราะห์), GSB (ธนาคารออมสิน), KBANK (กสิกรไทย), SCB (ไทยพาณิชย์), KTB (กรุงไทย), Chayo555
- **มาร์เก็ตเพลสอสังหาริมทรัพย์**: DDproperty, Livinginsider, NaYoo (น่าอยู่), Baania, ZmyHome

---

## วิธีรันด่วน (Quick Start)

> [!TIP]
> เพียงแค่ดับเบิ้ลคลิกไฟล์เดียว ระบบจะตรวจสอบ Python และ Environment ให้โดยอัตโนมัติ พร้อมเปิดหน้าเว็บแดชบอร์ดบนเบราว์เซอร์ทันที

1. ตรวจสอบว่าเครื่องมี **Python 3.10 ขึ้นไป** ([ดาวน์โหลด Python](https://www.python.org/downloads/))
   - ตอนติดตั้ง Python ให้เลือกเครื่องหมายถูกที่ช่อง **`Add python.exe to PATH`**
2. ดับเบิ้ลคลิกที่ไฟล์ **`run_dashboard.bat`**
3. ระบบจะเปิดหน้าเว็บ Dashboard บนเบราว์เซอร์ที่: **`http://localhost:8501`**

---

## โครงสร้างโปรเจกต์ (Clean Dashboard Architecture)

โปรเจกต์ได้รับการจัดระเบียบแบบ **Modular Architecture** เพื่อความเสถียรและประสิทธิภาพสูงสุด โดยมีเฉพาะไฟล์ที่จำเป็นสำหรับการรัน Dashboard:

```text
All Asset Dashboard/
│
├── [RUN]  run_dashboard.bat               # ตัวเปิด Dashboard อัตโนมัติ (ตรวจจับ .venv และ Libraries)
├── [SYNC] push_to_github.bat              # ซิงค์โค้ดและอัปเดตขึ้น GitHub ในคลิกเดียว
├── [UTIL] convert_csv_to_parquet.py       # สคริปต์แปลงไฟล์ CSV รายเดือนเป็น all_asset.parquet
│
├── [DATA] all_asset.parquet               # ฐานข้อมูลหลักของทรัพย์สิน NPA (~200,000+ รายการ)
├── [CFG]  requirements.txt                # รายการ Python Libraries ที่จำเป็น
├── [DOC]  README.md                       # เอกสารคู่มือการติดตั้งและใช้งาน
├── [DOC]  SECURITY.md                     # นโยบายความปลอดภัยและข้อมูล
│
├── [CORE] app.py                          # Entry point หลักของระบบ Streamlit (~118 บรรทัด)
├── [MOD]  bubble_chart.py                 # โมดูลสร้างกราฟ 3D Glossy Bubble Chart
├── [MOD]  dashboard_metrics.py            # โมดูลคำนวณ KPI และตัวชี้วัดทางการเงิน
├── [MOD]  sam_analytics.py                # ระบบจัดกลุ่มโครงการ & คำนวณราคากลางต่อพื้นที่
├── [MOD]  user_logger.py                  # ระบบบันทึกประวัติการเข้าชมและการใช้งาน
│
├── [DIR]  modules/                        # โครงสร้างโค้ดหลักแบบแยกส่วน (Modular)
│   ├── config/                            # การตั้งค่าระบบ, Theme CSS, ค่าคงที่ของบริษัท/ประเภททรัพย์
│   ├── services/                          # Data Loader, Cleaner, Geo Service (GIS), Export Service
│   ├── ui/                                # Welcome Portal Gateway, Sidebar Filters, KPI Header
│   └── views/                             # วิวแสดงผลของทั้ง 4 แท็บหลัก
│
├── [DIR]  data/                           # ข้อมูลขอบเขตเชิงพื้นที่ GIS (districts & subdistricts GeoJSON)
├── [DIR]  references/                     # ตารางอ้างอิงภูมิศาสตร์ไทย และ Template นำเข้าข้อมูล
├── [DIR]  logo/                           # โลโก้สถาบันการเงิน 14 แหล่ง, ไอคอนแอปพลิเคชัน และ Favicon
├── [DIR]  static/                         # ไฟล์ CSS สไตล์, Deck.gl Map Template, D3.js
└── [DIR]  .streamlit/                     # การตั้งค่า Streamlit Config (Theme, Server Ports)
```

---

## วิธีการรันผ่าน Terminal / Command Line (Manual)

หากต้องการติดตั้งและรันผ่าน Command Line:

1. **สร้าง Python Virtual Environment:**
   ```bash
   python -m venv .venv
   ```

2. **เปิดใช้งาน Environment:**
   - **Windows:**
     ```cmd
     .venv\Scripts\activate
     ```
   - **macOS / Linux:**
     ```bash
     source .venv/bin/activate
     ```

3. **ติดตั้ง Libraries:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **เริ่มรัน Dashboard:**
   ```bash
   streamlit run app.py
   ```

---

## การนำไป Host บน Server หรือใช้งานในวง LAN

หากต้องการรันบน Server หรือเปิดให้เครื่องอื่นในเครือข่ายเข้าใช้งาน:

```cmd
streamlit run app.py --server.port=8501 --server.address=0.0.0.0 --server.maxUploadSize=500
```

- เข้าใช้งานจากเครื่องอื่นในเครือข่าย: `http://<IP_เครื่อง_SERVER>:8501`

---

## ฟังก์ชันหลักของระบบ (Core Features)

### 1. ภาพรวม (Bubble Chart)
- **3D Glossy Bubble Chart**: กราฟฟองสบู่ 3 มิติเชิงโต้ตอบ แสดงการกระจายตัวของมูลค่าและจำนวนทรัพย์ตามกลุ่มประเภททรัพย์และภูมิภาค
- สรุปภาพรวมมูลค่าพอร์ตทรัพย์สินทั้งหมด (Total Portfolio Value) และจำนวนทรัพย์รวม

### 2. แผนที่ (Interactive Map)
- **GPU-Accelerated Deck.gl Map**: แผนที่ความหนาแน่นและพิกัดหมุดจริง รองรับการแสดงผลนับแสนรายการอย่างลื่นไหล
- **Polygon Boundary Layers**: แสดงขอบเขตระดับตำบล/อำเภอ/จังหวัด
- **รัศมีค้นหารอบจุดอ้างอิง (Radius Search)**: กำหนดพิกัดและค้นหาทรัพย์คู่แข่งในรัศมีที่กำหนด
- **Median Reference Analytics**: เปรียบเทียบราคากลางต่อตารางวา/ตารางเมตรในรัศมีเดียวกัน

### 3. สถิติ & วิเคราะห์ (Analytics)
- **การเปรียบเทียบระหว่างสถาบัน**: เจาะลึกราคาเฉลี่ยต่อตารางวา/ตารางเมตรแยกตามธนาคารและประเภททรัพย์
- **การวิเคราะห์โครงการเดียวกัน (Same Project Matching)**: ตรวจจับและรวมทรัพย์ที่อยู่ในโครงการเดียวกัน แม้สะกดชื่อต่างกัน
- การกระจายตัวของช่วงราคา (Price Distribution) และสัดส่วนทรัพย์สินแต่ละภูมิภาค

### 4. รายการทรัพย์สิน (Property Listing)
- ตารางแสดงรายการทรัพย์สินแบบละเอียด พร้อมระบบ Sorting และ Filtering ตามเงื่อนไขหลายมิติ
- ตรวจสอบรายละเอียดทรัพย์ รหัสทรัพย์ ลิงก์ตรงไปยังเว็บต้นทาง และรูปภาพทรัพย์
- **ระบบนำเข้าข้อมูลภายนอก (Custom Data Import)**: นำเข้าไฟล์ CSV/Excel ของผู้ใช้มารวมกับฐานข้อมูลกลางได้ชั่วคราว
- **ส่งออกข้อมูล (Export)**: ดาวน์โหลดผลการค้นหาเป็นไฟล์ Excel (.xlsx) และ CSV

---

## การอัปเดตข้อมูลรายเดือน (Data Refresh)

เมื่อมีไฟล์ข้อมูลสำรวจใหม่จากขั้นตอนการรวบรวมข้อมูล:
1. นำไฟล์ CSV ที่รวมข้อมูลแล้วมาวางไว้ในโฟลเดอร์โปรเจกต์
2. รันคำสั่งแปลงไฟล์เป็น Parquet:
   ```bash
   python convert_csv_to_parquet.py
   ```
3. ระบบจะสร้างและอัปเดตไฟล์ `all_asset.parquet` ใหม่ พร้อมใช้งานบน Dashboard ทันที
