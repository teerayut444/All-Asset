# 📚 บันทึกโครงสร้างและสถาปัตยกรรมการดึงข้อมูล (Web Scraper Architecture & Data Schema Reference)

เอกสารฉบับนี้รวบรวม **โครงสร้างเว็บ (Web Structure), Endpoint, Data Schema, และเทคนิคการดึงข้อมูล** ของทุกค่ายอสังหาริมทรัพย์และ NPA ทั้งหมด 13 แหล่งที่ใช้งานในระบบ All Asset Dashboard

---

## 📋 มาตรฐานข้อมูลกลาง (Standard 21 Columns)

ทุกสคริปต์สแครปเปอร์จะแปลงข้อมูลให้อยู่ในรูปแบบมาตรฐาน 21 คอลัมน์เดียวกันก่อนบันทึกเป็น CSV:

| # | ชื่อคอลัมน์ | ชนิดข้อมูล | คำอธิบาย & กฎการแปลง |
|---|---|---|---|
| 1 | **บริษัท** | Text | ชื่อค่าย เช่น `Baania`, `BAM`, `GSB`, `KBANK`, `KTB`, `SCB`, `GHB`, `SAM`, `NaYoo`, `ZmyHome`, `Chayo555`, `Taladnudbaan`, `LED` |
| 2 | **ID** | Text | Primary Key ไม่ซ้ำกันในระบบของค่ายนั้นๆ |
| 3 | **รหัสทรัพย์** | Text | รหัสอ้างอิงทรัพย์ (Property Code) หากไม่มีให้ใช้ `ID` แทน |
| 4 | **ชื่อโครงการ** | Text | ชื่อหมู่บ้าน/คอนโด/โครงการ (ถ้ามี) |
| 5 | **ประเภททรัพย์** | Text | แปลงเป็นหมวดมาตรฐาน (บ้านเดี่ยว, ห้องชุดพักอาศัย, ทาวน์เฮ้าส์, ที่ดินเปล่า, อาคารพาณิชย์, โรงงาน/โกดัง, โรงแรม/รีสอร์ท, อพาร์ทเมนท์, อาคารสำนักงาน) |
| 6 | **ประเภทการขาย** | Text | `ขาย`, `เช่า`, `ขาย/เช่า`, `ประมูล` |
| 7 | **ราคา** | Numeric (Float) | ราคาขาย/ราคาประเมิน (บาท) ห้ามมีคอมม่า |
| 8 | **ตำบล** | Text | ตำบล/แขวง (ตัดคำนำหน้า 'ต.', 'แขวง' ออก) |
| 9 | **อำเภอ** | Text | อำเภอ/เขต (ตัดคำนำหน้า 'อ.', 'เขต' ออก) |
| 10 | **จังหวัด** | Text | ชื่อจังหวัดมาตรฐาน เช่น `กรุงเทพมหานคร`, `ชลบุรี`, `เชียงใหม่` |
| 11 | **ละติจูด** | Numeric (Float) | พิกัด WGS84 Latitude |
| 12 | **ลองจิจูด** | Numeric (Float) | พิกัด WGS84 Longitude |
| 13 | **ชื่อประกาศ** | Text | หัวข้อประกาศ หรือสร้างจาก `ประเภท + โครงการ + ตำบล อำเภอ จังหวัด` |
| 14 | **ลิงก์** | Text | URL หน้าประกาศตรงของทรัพย์ |
| 15 | **เนื้อที่ (ตร.ว.)** | Text | รูปแบบ `ไร่-งาน-ตร.ว.` เช่น `1-2-50`, `0-0-25.5` |
| 16 | **พื้นที่ใช้สอย (ตร.ม.)** | Numeric (Float) | ขนาดพื้นที่ใช้สอยตัวอาคาร |
| 17 | **วันที่ดึงข้อมูล** | Datetime | รูปแบบ `YYYY-MM-DD HH:MM:SS` |
| 18 | **ห้องนอน** | Numeric (Int) | จำนวนห้องนอน |
| 19 | **ห้องน้ำ** | Numeric (Int) | จำนวนห้องน้ำ |
| 20 | **ที่จอดรถ** | Numeric (Int) | จำนวนที่จอดรถ |
| 21 | **วันประกาศ** | Text/Date | วันที่ลงประกาศ หรือวันที่อัปเดตข้อมูลล่าสุด |

---

## 🏛️ โครงสร้างของแต่ละเว็บไซต์ (Platform Specifications)

---

### 1. Baania (`scrape_baania_monthly.py`)
- **ประเภทเว็บ**: Next.js SSR Web Application (ElasticSearch Backend Payload)
- **Engine**: `curl_cffi` (Impersonate: `chrome120`)
- **Listing URL**: `https://www.baania.com/s/%E0%B8%97%E0%B8%B1%E0%B9%89%E0%B8%87%E0%B8%AB%E0%B8%A1%E0%B8%94/listing?sellState=on-sale,sale-rent&sort.created=asc&page={page}`
- **Items Per Page**: 48 รายการ/หน้า (จำกัดสูงสุด 208 หน้า ~ 10,000 รายการตาม ElasticSearch window)
- **เทคนิคการดึงข้อมูล**:
  - ดึง HTML แล้วใช้ Regex สกัด JSON จาก `<script id="__NEXT_DATA__" type="application/json">(.*?)</script>`
  - ดึงรายการจาก Path: `props.pageProps.defaultData.hits.hits`
- **Field Mapping**:
  - `ID`: `item._id` หรือ `_source.view_data.pkid`
  - `รหัสทรัพย์`: `_source.view_data.code` (หากว่างใช้ `ID`)
  - `ชื่อโครงการ`: `_source.view_data.project_title.th`
  - `ชื่อประกาศ`: `_source.view_data.title.th`
  - `ประเภททรัพย์`: `_source.view_data.property_type[].th`
  - `ประเภทการขาย`: แปลงจาก `_source.view_data.sell_state` หรือ `_source.view_data.listing_type`
  - `ราคา`: `_source.view_data.price_start` ➡️ `price` ➡️ `price_rent` ➡️ `_source.filter.price[0]`
  - `ที่อยู่`: 
    - ตำบล: `_source.address.subdistrict.title.th`
    - อำเภอ: `_source.address.district.title.th`
    - จังหวัด: `_source.address.province.title.th`
  - `พิกัด`: `_source.location.lat`, `_source.location.lon`
  - `เนื้อที่`: `_source.view_data.area_total` (`rai`, `ngan`, `wa`) ➡️ แปลงเป็น `ไร่-งาน-ตร.ว.`
  - `พื้นที่ใช้สอย`: `_source.view_data.area_usable`
  - `ลิงก์`: `https://www.baania.com/th/{url.source_url}` หรือ `https://www.baania.com/th/listing/{slug|id}`
  - `วันประกาศ`: `_source.filter.created` หรือ `_source.view_data.created_at`
  - `ห้องนอน/ห้องน้ำ/ที่จอดรถ`: `_source.view_data.bedroom`, `bathroom`, `parking`

---

### 2. BAM - บมจ.บริหารสินทรัพย์ กรุงเทพพาณิชย์ (`scrape_bam_monthly.py`)
- **ประเภทเว็บ**: Server-rendered Search Page + Detail Page Scraping
- **Engine**: `requests` + `BeautifulSoup` + Regex
- **Listing URL**: `https://www.bam.co.th/th/npa/property/search?page={page}`
- **Detail URL**: `https://www.bam.co.th/th/npa/property/{item_id}`
- **Items Per Page**: 24 รายการ/หน้า (~18,000+ รายการ)
- **เทคนิคการดึงข้อมูล**:
  - สกัดรายการทรัพย์และ metadata จาก JSON state ใน HTML หน้าค้นหา
  - ดึงข้อมูลพิกัดและที่อยู่ละเอียดเพิ่มเติมจาก OpenGraph meta (`og:description`) และ Google Maps embed ในหน้า Detail
- **Field Mapping**:
  - `ID` / `รหัสทรัพย์`: รหัสทรัพย์ BAM เช่น `HP-XXXXX`
  - `ราคา`: สกัดจากข้อความราคา หรือ JSON payload
  - `ที่อยู่`: แยกจากสตริง `ตำบล, อำเภอ, จังหวัด` ใน meta tag
  - `เนื้อที่`: แยกคำนวณ ไร่-งาน-วา จากข้อความรายละเอียด

---

### 3. KTB - ธนาคารกรุงไทย NPA (`scrape_ktb_monthly.py`)
- **ประเภทเว็บ**: REST API (JSON POST Endpoint)
- **Engine**: `requests` (AuditedSession)
- **Endpoint**: `POST https://npa.krungthai.com/api/v1/product/searchAll`
- **Headers**: `Content-Type: application/json`, `Referer: https://npa.krungthai.com/searchResult`
- **Request Payload**:
  ```json
  {
    "paging": {
      "currentPage": 1,
      "rowsPerPage": 50,
      "totalRows": 0
    }
  }
  ```
- **Response Format**: `dataResponse` (Array of objects), `paging.totalRows`
- **Field Mapping**:
  - `ID`: `item.collGrpId` หรือ `item.collCode`
  - `รหัสทรัพย์`: `item.collCode`
  - `ชื่อโครงการ`: `item.projectName`
  - `ประเภททรัพย์`: `item.propTypeDesc`
  - `ราคา`: `item.sellPrice` หรือ `item.appraisePrice`
  - `ที่อยู่`: `item.tumbolName`, `item.amphurName`, `item.provinceName`
  - `พิกัด`: `item.latitude`, `item.longitude`
  - `เนื้อที่`: คำนวณจาก `item.rai`, `item.ngan`, `item.wah`
  - `พื้นที่ใช้สอย`: `item.usableArea`
  - `ลิงก์`: `https://npa.krungthai.com/detail/{collGrpId}`

---

### 4. SCB - ธนาคารไทยพาณิชย์ Home SCB (`scrape_scb_monthly.py`)
- **ประเภทเว็บ**: REST API (AJAX JSON Endpoint)
- **Engine**: `requests` (AuditedSession)
- **Endpoint**: `GET https://asset.home.scb/api/project/cmd`
- **Query Params**:
  ```
  type=project&page={page}&limit=50&sortBy=all&command=get_project
  ```
- **Response Format**: `{"s": "y", "total": 1234, "d": [...]}`
- **Field Mapping**:
  - `ID`: `item.project_id`
  - `ชื่อโครงการ`: `item.project_name`
  - `ประเภททรัพย์`: `item.property_type_name`
  - `ราคา`: `item.special_price` หรือ `item.sale_price`
  - `ที่อยู่`: สกัดจาก `item.address_full` ด้วย Regex หรือฟิลด์ `province_name`, `district_name`, `subdistrict_name`
  - `พิกัด`: `item.lat`, `item.lng`
  - `ลิงก์`: `https://asset.home.scb/project/{project_id}`

---

### 5. GSB - ธนาคารออมสิน NPA (`scrape_gsb_monthly.py`)
- **ประเภทเว็บ**: Next.js Static Build Data API
- **Engine**: `subprocess` (`curl.exe` with `x-nextjs-data: 1`)
- **Build ID Extraction**: ดึง Build ID จากหน้าแรก `https://npa-assets.gsb.or.th/`
- **Data Endpoint**: `https://npa-assets.gsb.or.th/_next/data/{build_id}/asset/npa/all.json`
- **Response Format**: Next.js props JSON บรรจุรายการทรัพย์ทั้งหมดในไฟล์เดียว
- **Field Mapping**:
  - `ID`: `item.asset_id` หรือ `item.id`
  - `รหัสทรัพย์`: `item.asset_group_id_npa` หรือ `item.asset_group_id`
  - `ประเภททรัพย์`: `item.asset_type_desc`
  - `ราคา`: `item.xprice` ➡️ `item.current_offer_price` ➡️ `item.xprice_normal`
  - `ที่อยู่`: `item.sub_district_name`, `item.district_name`, `item.province_name`
  - `พิกัด`: `item.latitude`, `item.longitude`
  - `เนื้อที่`: `item.rai`, `item.ngan`, `item.wa`
  - `ลิงก์`: `https://npa-assets.gsb.or.th/asset/{dev_type}/{asset_id}`

---

### 6. KBANK - ธนาคารกสิกรไทย NPA (`scrape_kbank_monthly.py`)
- **ประเภทเว็บ**: ASP.NET Web Service + Akamai Interstitial Challenge
- **Engine**: `curl_cffi` (Impersonate: `chrome120`)
- **Security / WAF**: Akamai Interstitial POW Solver (`solve_akamai_challenge`)
- **Endpoint**: `POST https://www.kasikornbank.com/Custom/KWEB2020/NPA2023Backend13.aspx/GetProperties`
- **Payload**:
  ```json
  {
    "filter": {
      "AllCurrentPageIndex": 1,
      "CurrentPageIndex": 1,
      "PageSize": 50,
      "SearchPurposes": ["AllProperties"],
      "propertyList": "AllProperties"
    }
  }
  ```
- **Response Format**: `{"d": "{\"Data\": {\"TotalRows\": 1234, \"Items\": [...]}}"}`
- **Field Mapping**:
  - `ID` / `รหัสทรัพย์`: `item.PropertyCode` หรือ `item.PropertyId`
  - `ชื่อโครงการ`: `item.ProjectName`
  - `ประเภททรัพย์`: `item.PropertyTypeDesc`
  - `ราคา`: `item.SpecialPrice` หรือ `item.Price`
  - `ที่อยู่`: `item.SubDistrictName`, `item.DistrictName`, `item.ProvinceName`
  - `พิกัด`: `item.Latitude`, `item.Longitude`
  - `ลิงก์`: `https://www.kasikornbank.com/th/propertyforsale/search/pages/detail.aspx?PropertyCode={PropertyCode}`

---

### 7. GHB - ธนาคารอาคารสงเคราะห์ (`scrape_ghb_monthly.py`)
- **ประเภทเว็บ**: Server-rendered HTML + Detail Page Coordination
- **Engine**: `curl_cffi` (Impersonate: `chrome120`) + `BeautifulSoup`
- **Listing URL**: `https://www.ghbhomecenter.com/property-for-sale?pg={page_no}`
- **Detail URL**: `https://www.ghbhomecenter.com/property-{pid}`
- **Items Per Page**: 20 รายการ/หน้า (~30,000+ รายการ)
- **Field Mapping**:
  - `ID`: รหัสตัวเลขจาก URL `/property-{pid}`
  - `ราคา`: สกัดจาก `class="text-propertyprice"`
  - `ที่อยู่`: สกัดจาก card description
  - `พิกัด & ห้อง`: สกัดจากตัวแปร JavaScript `var geoLat = ...`, `var geoLong = ...` ในหน้า Detail

---

### 8. SAM - บริษัท บริหารสินทรัพย์สุขุมวิท จำกัด (`scrape_sam_monthly.py`)
- **ประเภทเว็บ**: PHP Search Backend + Detail HTML Page
- **Engine**: `requests` + `BeautifulSoup`
- **Listing Endpoint**: `POST https://sam.or.th/site/npa/page_list.php`
- **Detail Endpoint**: `GET https://sam.or.th/site/npa/detail.php?id={prop_id}&keyref=`
- **Field Mapping**:
  - `ID` / `รหัสทรัพย์`: `รหัสทรัพย์สิน : XXXXX`
  - `ประเภททรัพย์`: `ประเภททรัพย์สิน : ...`
  - `ราคา`: `ราคาประกาศขาย : ...`
  - `ที่อยู่`: สกัดจากข้อความที่ตั้ง `ตำบล... อำเภอ... จังหวัด...`
  - `พิกัด`: สกัดจาก Google Maps Embed link ในหน้า Detail

---

### 9. NaYoo - น่าอยู่ (`scrape_nayoo_monthly.py`)
- **ประเภทเว็บ**: Modern Multi-tenant REST API
- **Engine**: `requests` (AuditedSession)
- **API Base**: `https://api.nayoo.co`
- **GIS Reverse Geocoding**: เชื่อมต่อกับโมเดล Shapefile/GeoJSON (`subdistricts.geojson`) ด้วย `shapely.strtree.STRtree` สำหรับแปลงพิกัด (Lat/Lon) เป็น ตำบล/อำเภอ/จังหวัด อัตโนมัติเมื่อเว็บไม่มีชื่อที่อยู่
- **Field Mapping**:
  - `ID`: `item.id` หรือ `item.uuid`
  - `ชื่อโครงการ`: `item.project_name.th` หรือ `item.title`
  - `ราคา`: `item.price` หรือ `item.min_price`
  - `ที่อยู่`: สกัดจาก API หรือ Reverse geocode ผ่าน GeoJSON
  - `พิกัด`: `item.latitude`, `item.longitude`
  - `ลิงก์`: `https://nayoo.co/listings/{slug}`

---

### 10. ZmyHome (`scrape_zmyhome_monthly.py`)
- **ประเภทเว็บ**: Next.js / Server-rendered Listing + Multi-threading Concurrent Workers
- **Engine**: `requests` (AuditedSession) + `BeautifulSoup` + `ThreadPoolExecutor(max_workers=5)`
- **GIS Reverse Geocoding**: In-Memory `shapely.strtree.STRtree` + `subdistricts.geojson` (คำนวณใน RAM <0.1ms ไม่มีการยิง OpenStreetMap API ภายนอก)
- **Listing URL**: `https://zmyhome.com/buy?page={page}&sortFilter=ads&per-page=35`
- **Detail URL**: `https://zmyhome.com/property/{item_id}`
- **Items Per Page**: 35 รายการ/หน้า (~32,500+ รายการ)
- **Field Mapping**:
  - `ID` / `รหัสทรัพย์`: รหัสทรัพย์จาก URL เช่น `V206959`, `H451280`
  - `ชื่อโครงการ`: สกัดจาก `info-project` หรือ Breadcrumbs
  - `ประเภททรัพย์`: แปลงจาก Breadcrumbs หรือ ID Prefix (`V` = ห้องชุดพักอาศัย, `H` = บ้านเดี่ยว)
  - `ราคา`: สกัดจาก Card Price / JSON-LD Offer (`priceSpecification`)
  - `ที่อยู่`: Reverse geocode จากพิกัด Lat/Lng ผ่าน Shapely STRtree In-Memory GIS 100% (ไม่ใช้ข้อมูลที่อยู่ดิบจาก Card/HTML เพื่อป้องกันชื่อสถานีรถไฟฟ้า/ซอยมาปน)
  - `พิกัด`: สกัดจาก Google Maps Embed link หรือตัวแปร Leaflet ในหน้า Detail
  - `เนื้อที่ & พื้นที่ใช้สอย`: สกัดจาก `og:description` และข้อความรายละเอียดตัวบ้าน
  - `ห้องนอน/ห้องน้ำ/ที่จอดรถ`: สกัดจากสเปคยูนิตในหน้า Detail

---

### 11. Chayo555 - ชโย กรุ๊ป (`scrape_chayo555_monthly.py`)
- **ประเภทเว็บ**: Asset Listing Web Portal
- **Engine**: `requests` + `BeautifulSoup` + GeoJSON Engine
- **Listing URL**: `https://asset.chayo555.com`
- **Field Mapping**:
  - `ID` / `รหัสทรัพย์`: รหัสทรัพย์ชโย
  - `ราคา`: ราคาขายทรัพย์ NPA
  - `ที่อยู่ & พิกัด`: สกัดจาก Card HTML และแปลงพิกัดผ่าน GIS Engine

---

### 12. Taladnudbaan - ตลาดนัดบ้านมือสอง (`scrape_taladnudbaan_monthly.py`)
- **ประเภทเว็บ**: Paginated HTML Property Portal
- **Engine**: `requests` + `BeautifulSoup`
- **Listing URL**: `https://www.taladnudbaan.com/properties?page={page_num}`
- **Detail URL**: `https://www.taladnudbaan.com/property/{slug_id}`
- **Field Mapping**:
  - `ID`: รหัสอสังหาฯ จาก URL
  - `ราคา`: สกัดจากราคาประกาศขาย
  - `ที่อยู่`: แยกข้อความ ตำบล อำเภอ จังหวัด

---

### 13. LED - กรมบังคับคดี (`scrape_led_monthly.py`)
- **ประเภทเว็บ**: ASP.NET / ASP Web Forms (Table Search)
- **Engine**: `requests` (Session with State management)
- **Base URL**: `https://asset.led.go.th/newbidreg/`
- **Search URL**: `https://asset.led.go.th/newbidreg/default.asp`
- **เทคนิคการดึงข้อมูล**:
  - ดึงค่า `oseckey` และรายชื่อจังหวัดจากหน้าเริ่มต้น
  - ส่ง POST Form request ค้นหาตามรายจังหวัด
  - สกัดฟอร์มทรัพย์ (`web1`, `web2`, ...) และ input hidden fields
- **Field Mapping**:
  - `ID`: `auc_asset_gen` หรือ `{law_suit_no}/{law_suit_year}_{str_bid_num}`
  - `รหัสทรัพย์`: คดีหมายเลขแดง/ลำดับทรัพย์
  - `ประเภทการขาย`: `saletypename` (เช่น `ประมูล`)
  - `ราคา`: `assetprice1` ถึง `assetprice9` (ค้นหาราคาประเมินที่ไม่เป็น 0)
  - `ที่อยู่`: `tumbol_name`, `amphur_name`, `province_name`
  - `เนื้อที่`: `rai`, `ngan`, `wa`
  - `ลิงก์`: `https://asset.led.go.th/newbidreg/asset_open.asp?law_suit_no=...`

---

## 🛡️ กฎการตรวจสอบความถูกต้องของข้อมูล (Quality & Resume Rule)

1. **Smart Resume Validation**:
   - เมื่อโหลดไฟล์ CSV สะสมเดิม หากพบว่าข้อมูลเดิมมากกว่า 50% มีค่าว่างในคอลัมน์สำคัญ (เช่น `ราคา` หรือ `จังหวัด` เป็น `NaN`) ระบบจะทำการ**ละทิ้งข้อมูลที่ไม่สมบูรณ์และเริ่มสแครปใหม่**ทันที เพื่อป้องกันการข้ามหน้าจากการบันทึกที่ผิดพลาดในอดีต
2. **Rate Limiting & Safety Delays**:
   - ค่ายที่ใช้ Next.js/ElasticSearch (เช่น Baania, GSB) เว้นระยะ 2.5 - 4.0 วินาที
   - ค่ายธนาคารที่มี WAF เข้มงวด (เช่น KBANK, GHB) เว้นระยะ 6.0 - 11.0 วินาที
3. **Encoding & Text Sanitization**:
   - ใช้ `sys.stdout.reconfigure(encoding='utf-8')` ทุกสคริปต์
   - บันทึกไฟล์ CSV ด้วย `encoding='utf-8-sig'` เพื่อให้เปิดใน Microsoft Excel ภาษาไทยได้อย่างถูกต้อง
