# 🏢 All Asset NPA Dashboard & Market Intelligence System

ระบบแดชบอร์ดวิเคราะห์และเปรียบเทียบข้อมูลทรัพย์สินรอการขาย (NPA) ครบวงจร ครอบคลุมสถาบันการเงินและแพลตฟอร์มอสังหาริมทรัพย์ชั้นนำกว่า 12 แหล่งในประเทศไทย พร้อมระบบแผนที่ Interactive พิกัดจริง และการประเมินราคากลางเชิงลึก

---

## 📁 โครงสร้างโปรเจกต์ (Project Structure)

```text
├── app.py                      # แอปพลิเคชันหลัก (Streamlit Web Dashboard)
├── sam_analytics.py            # โมดูลวิเคราะห์โครงการเดียวกัน & สถิติเชิงลึก
├── bubble_chart.py             # โมดูล 3D Glossy Bubble Chart
├── dashboard_metrics.py        # โมดูลคำนวณ KPI และเมตริกภาพรวม
├── all_assets.parquet          # ฐานข้อมูลหลักของระบบ (~200,000+ รายการ)
├── requirements.txt            # รายการ Python Libraries ที่จำเป็น
├── run_dashboard.bat           # ไฟล์ Batch Script สำหรับเปิดใช้งานบน Windows
├── assets/                     # โฟลเดอร์รูปภาพ โลโก้ และ Pin แผนที่
│   ├── logo.png
│   └── logos/
├── Monthly all new/            # โฟลเดอร์ระบบ Scraping ข้อมูล 12 ค่าย (รายเดือน)
├── backups/                    # โฟลเดอร์เก็บไฟล์สำรองและเวอร์ชันก่อนหน้า
└── README.md                   # คู่มือการใช้งานและเอกสารประกอบ
```

---

## 🚀 วิธีการติดตั้งและรันใช้งาน (Local / Development)

1. **สร้าง Python Virtual Environment:**
   ```bash
   python -m venv .venv
   ```

2. **เปิดใช้งาน Environment:**
   - **Windows:** `.\.venv\Scripts\activate`
   - **Linux / macOS:** `source .venv/bin/activate`

3. **ติดตั้ง Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **เริ่มรัน Dashboard:**
   ```bash
   streamlit run app.py
   ```
   *หรือดับเบิลคลิกไฟล์ `run_dashboard.bat` (บน Windows)*

---

## 🌐 การนำไป Host บนเครื่อง Server (Production Deployment)

สั่งรันด้วยพารามิเตอร์เพื่อให้เครื่องอื่นในเครือข่ายสามารถเข้าใช้งานได้:
```bash
streamlit run app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true
```

- เข้าใช้งานผ่านเบราว์เซอร์: `http://<SERVER_IP>:8501`

---

## 📊 ฟังก์ชันหลักของระบบ (Core Features)

1. 🔮 **ภาพรวม & แผนที่ (Bubble & Map)**: ดูภาพรวมสัดส่วนพอร์ตโฟลิโอ 3D Bubble Chart และแผนที่ความหนาแน่นรายจังหวัด
2. 📈 **สถิติ & วิเคราะห์ (Analytics)**: สถิติภาพรวมตลาด วิเคราะห์ช่วงราคา และการกระจายตัวพอร์ต SAM
3. 🔍 **เปรียบเทียบตำแหน่ง (Comparison)**:
   - 📍 *ค้นหาตามรัศมีทำเล*: เปรียบเทียบทรัพย์รอบจุดอ้างอิง พร้อมคำนวณราคาต่อตารางวา/ตารางเมตร
   - 🏘️ *เปรียบเทียบในโครงการเดียวกัน*: เจาะลึกทรัพย์ทุกยูนิตในโครงการเดียวกัน พร้อมแผนที่ Logo Pin
4. 📋 **รายการทรัพย์สิน (Property Listing)**: ตารางค้นหา กรอง และส่งออกข้อมูล Excel/CSV

