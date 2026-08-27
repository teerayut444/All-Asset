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
├── 🚀 start_dashboard.bat        # ดับเบิ้ลคลิกเพื่อสร้าง .venv ติดตั้ง และรัน Dashboard
├── 📄 requirements.txt           # รายการ Python Libraries ที่จำเป็น
├── 📄 all_assets.parquet         # ฐานข้อมูลหลักของทรัพย์สิน NPA (~200,000+ รายการ)
├── 📄 README.md                  # เอกสารคู่มือการติดตั้งและใช้งาน
│
├── 🐍 app.py                     # แอปพลิเคชันหลัก (Streamlit Web Dashboard)
├── 🐍 sam_analytics.py           # โมดูลวิเคราะห์โครงการเดียวกัน & สถิติเชิงลึก
├── 🐍 bubble_chart.py            # โมดูล 3D Glossy Bubble Chart
├── 🐍 dashboard_metrics.py       # โมดูลคำนวณ KPI และเมตริกภาพรวม
├── 🐍 chart_3d_analytics.py      # โมดูลกราฟ 3D Interactive Analytics
│
├── 📁 .streamlit/                # ตั้งค่า Theme และ Streamlit Server (config.toml)
├── 📁 assets/                    # รูปภาพ Logo และโลโก้สถาบันการเงิน (logos/)
└── 📁 static/                    # ไฟล์ Static และแผนที่ (d3.js, deck.gl.js, map_template.html)
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
