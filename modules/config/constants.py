import re
import numpy as np
import pandas as pd

# Thai Administrative Regions Mapping
REGION_PROVINCES = {
    'ภาคกลาง': [
        'กรุงเทพมหานคร', 'นนทบุรี', 'ปทุมธานี', 'สมุทรปราการ', 'สมุทรสาคร', 'สมุทรสงคราม',
        'นครปฐม', 'พระนครศรีอยุธยา', 'สระบุรี', 'ลพบุรี', 'สุพรรณบุรี', 'ชัยนาท', 'สิงห์บุรี', 'อ่างทอง'
    ],
    'ภาคเหนือ': [
        'เชียงใหม่', 'เชียงราย', 'ลำปาง', 'ลำพูน', 'แม่ฮ่องสอน', 'น่าน', 'พะเยา', 'แพร่',
        'อุตรดิตถ์', 'พิษณุโลก', 'สุโขทัย', 'เพชรบูรณ์', 'พิจิตร', 'กำแพงเพชร', 'นครสวรรค์', 'อุทัยธานี', 'ตาก'
    ],
    'ภาคตะวันออกเฉียงเหนือ': [
        'นครราชสีมา', 'ขอนแก่น', 'อุดรธานี', 'อุบลราชธานี', 'ร้อยเอ็ด', 'บุรีรัมย์', 'สุรินทร์',
        'ศรีสะเกษ', 'มหาสารคาม', 'ชัยภูมิ', 'กาฬสินธุ์', 'สกลนคร', 'นครพนม', 'มุกดาหาร',
        'ยโสธร', 'อำนาจเจริญ', 'หนองคาย', 'เลย', 'หนองบัวลำภู', 'บึงกาฬ'
    ],
    'ภาคตะวันออก': [
        'ชลบุรี', 'ระยอง', 'ฉะเชิงเทรา', 'จันทบุรี', 'ตราด', 'นครนายก', 'ปราจีนบุรี', 'สระแก้ว'
    ],
    'ภาคตะวันตก': [
        'กาญจนบุรี', 'ราชบุรี', 'เพชรบุรี', 'ประจวบคีรีขันธ์'
    ],
    'ภาคใต้': [
        'ภูเก็ต', 'สุราษฎร์ธานี', 'สงขลา', 'นครศรีธรรมราช', 'กระบี่', 'พังงา', 'ตรัง',
        'ชุมพร', 'ระนอง', 'พัทลุง', 'สตูล', 'ปัตตานี', 'ยะลา', 'นราธิวาส'
    ]
}

PROVINCE_TO_REGION = {p: r for r, plist in REGION_PROVINCES.items() for p in plist}

# Global Company Brand Colors
COMPANY_COLORS = {
    "LED": "#0891b2",
    "SAM": "#10b981", 
    "BAM": "#3b82f6", 
    "Chayo555": "#f97316", 
    "Chayo": "#f97316", 
    "Chayo NPA": "#f97316", 
    "GHB": "#ca8a04", 
    "KBANK": "#059669", 
    "KTB": "#0284c7", 
    "SCB": "#7e22ce", 
    "GSB": "#eb1985",
    "DDproperty": "#a855f7",
    "Livinginsider": "#14b8a6",
    "NaYoo": "#8b5cf6", 
    "ZmyHome": "#ec4899",
    "Baania": "#f59e0b"
}
COMP_BRAND_COLORS = COMPANY_COLORS

# Gradient Palettes for Charts
COMP_GRADIENT_PALETTES = {
    "LED": ["#0e7490", "#0891b2", "#06b6d4", "#22d3ee", "#38bdf8", "#7dd3fc"],
    "SAM": ["#047857", "#059669", "#10b981", "#34d399", "#6ee7b7", "#a7f3d0"],
    "BAM": ["#1d4ed8", "#2563eb", "#3b82f6", "#60a5fa", "#93c5fd", "#bfdbfe"],
    "Chayo555": ["#c2410c", "#ea580c", "#f97316", "#fb923c", "#fdba74", "#fed7aa"],
    "Chayo": ["#c2410c", "#ea580c", "#f97316", "#fb923c", "#fdba74", "#fed7aa"],
    "Chayo NPA": ["#c2410c", "#ea580c", "#f97316", "#fb923c", "#fdba74", "#fed7aa"],
    "GHB": ["#a16207", "#ca8a04", "#eab308", "#facc15", "#fde047", "#fef08a"],
    "KBANK": ["#064e3b", "#047857", "#059669", "#10b981", "#34d399", "#6ee7b7"],
    "KTB": ["#075985", "#0369a1", "#0284c7", "#38bdf8", "#7dd3fc", "#bae6fd"],
    "SCB": ["#581c87", "#6b21a8", "#7e22ce", "#9333ea", "#a855f7", "#c084fc"],
    "GSB": ["#86198f", "#a21caf", "#c026d3", "#d946ef", "#f472b6", "#fbcfe8"],
    "DDproperty": ["#701a75", "#86198f", "#9333ea", "#a855f7", "#c084fc", "#e9d5ff"],
    "Livinginsider": ["#115e59", "#0d9488", "#14b8a6", "#2dd4bf", "#5eead4", "#99f6e4"],
    "NaYoo": ["#312e81", "#3730a3", "#4338ca", "#6366f1", "#818cf8", "#a5b4fc"],
    "ZmyHome": ["#881337", "#9f1239", "#be123c", "#e11d48", "#f43f5e", "#fda4af"],
    "Baania": ["#78350f", "#92400e", "#b45309", "#d97706", "#f59e0b", "#fde68a"]
}

def get_gradient_palette(comp_name, count=6):
    palette = COMP_GRADIENT_PALETTES.get(comp_name, ["#3b82f6"] * 6)
    if count == len(palette):
        return palette
    elif count < len(palette):
        indices = np.linspace(0, len(palette) - 1, count, dtype=int)
        return [palette[i] for i in indices]
    else:
        return palette + [palette[-1]] * (count - len(palette))

def get_region_by_province(prov):
    return PROVINCE_TO_REGION.get(str(prov).strip(), 'อื่นๆ / ไม่ระบุ')

def is_true_centroid(val, company=None):
    """Safely checks if a value represents a centroid coordinate, avoiding the Python bool(np.nan) == True gotcha."""
    if company is not None and str(company).strip().upper() == 'LED':
        return True
    if val is None or pd.isna(val):
        return False
    if isinstance(val, (bool, np.bool_)):
        return bool(val)
    if isinstance(val, (int, float, np.number)):
        return bool(val != 0)
    s = str(val).strip().lower()
    return s in ['true', '1', 'yes', 't']

PRICE_TIER_ORDER = [
    "< 1 ล้านบาท",
    "1 - 3 ล้านบาท",
    "3 - 5 ล้านบาท",
    "5 - 10 ล้านบาท",
    "10 - 20 ล้านบาท",
    "> 20 ล้านบาท"
]

def get_price_tier(price):
    """Classify a numeric property price into standardized Thai price tiers."""
    if pd.isna(price) or price is None or price <= 0:
        return "ไม่ระบุราคา"
    if price < 1_000_000:
        return "< 1 ล้านบาท"
    elif price < 3_000_000:
        return "1 - 3 ล้านบาท"
    elif price < 5_000_000:
        return "3 - 5 ล้านบาท"
    elif price < 10_000_000:
        return "5 - 10 ล้านบาท"
    elif price < 20_000_000:
        return "10 - 20 ล้านบาท"
    else:
        return "> 20 ล้านบาท"

INVALID_LOC_VALUES = {"", "nan", "none", "null", "undefined", "-", "ไม่มีข้อมูล", "ไม่ระบุ"}

PROMINENT_TYPES = [
    "บ้านเดี่ยว", "ห้องชุดพักอาศัย", "ทาวน์เฮ้าส์", "ที่ดินเปล่า",
    "อาคารพาณิชย์", "วิลล่า", "โรงงาน/โกดัง", "บ้านแฝด",
    "อพาร์ทเมนท์", "อาคารสำนักงาน", "โรงแรม/รีสอร์ท"
]

PROPERTY_TYPE_MAPPING = {
    # 1. หมวดบ้านเดี่ยว
    "บ้าน": "บ้านเดี่ยว",
    "บ้านครึ่งตึกครึ่งไม้": "บ้านเดี่ยว",
    "บ้านพร้อมกิจการ": "บ้านเดี่ยว",
    "Detached House": "บ้านเดี่ยว",
    "Single House": "บ้านเดี่ยว",
    "House": "บ้านเดี่ยว",
    
    # 2. หมวดคอนโดมิเนียม / ห้องชุด
    "คอนโด": "ห้องชุดพักอาศัย",
    "คอนโดมิเนียม": "ห้องชุดพักอาศัย",
    "ห้องชุด": "ห้องชุดพักอาศัย",
    "ห้องชุด/คอนโดมิเนียม": "ห้องชุดพักอาศัย",
    "ห้องชุด/ตอนโดมิเนียม": "ห้องชุดพักอาศัย",
    "คอนโดมิเนียม/อาคารชุด": "ห้องชุดพักอาศัย",
    "คอนโด/อาคารชุด/ห้องชุด": "ห้องชุดพักอาศัย",
    "Condo": "ห้องชุดพักอาศัย",
    "Condominium": "ห้องชุดพักอาศัย",
    "Penthouse": "ห้องชุดพักอาศัย",
    "Duplex": "ห้องชุดพักอาศัย",
    
    # 3. หมวดทาวน์เฮ้าส์ / ทาวน์โฮม
    "ทาวน์โฮม": "ทาวน์เฮ้าส์",
    "ทาวน์เฮาส์": "ทาวน์เฮ้าส์",
    "Townhouse": "ทาวน์เฮ้าส์",
    "Townhome": "ทาวน์เฮ้าส์",
    "Town House": "ทาวน์เฮ้าส์",
    "Town Home": "ทาวน์เฮ้าส์",
    
    # 4. หมวดที่ดิน
    "ที่ดิน": "ที่ดินเปล่า",
    "ที่ดินเปล่า": "ที่ดินเปล่า",
    "ที่ดินเกษตรกรรม": "ที่ดินเปล่า",
    "ที่ดินว่างเปล่า": "ที่ดินเปล่า",
    "ที่ดินพร้อมสิ่งปลูกสร้าง": "ที่ดินพร้อมสิ่งปลูกสร้าง",
    "สวนเกษตร": "ที่ดินเปล่า",
    "Land": "ที่ดินเปล่า",
    "Land with Building": "ที่ดินพร้อมสิ่งปลูกสร้าง",
    "Land with Buildings": "ที่ดินพร้อมสิ่งปลูกสร้าง",
    
    # 5. หมวดบ้านแฝด
    "บ้านแฝด": "บ้านแฝด",
    "Semi-Detached House (Twin House)": "บ้านแฝด",
    "Semi-Detached House": "บ้านแฝด",
    "Semi-detached House": "บ้านแฝด",
    "Twin House": "บ้านแฝด",
    
    # 6. หมวดวิลล่า
    "วิลล่า": "วิลล่า",
    "Villa": "วิลล่า",
    "Pool Villa": "วิลล่า",
    
    # 7. หมวดโรงงาน / โกดัง
    "โรงงาน": "โรงงาน/โกดัง",
    "โกดัง": "โรงงาน/โกดัง",
    "อาคารโรงงาน": "โรงงาน/โกดัง",
    "โกดัง/โรงงาน": "โรงงาน/โกดัง",
    "โกดัง / โรงงาน": "โรงงาน/โกดัง",
    "มินิแฟคตอรี่": "โรงงาน/โกดัง",
    "โรงสี": "โรงงาน/โกดัง",
    "Factory": "โรงงาน/โกดัง",
    "Warehouse": "โรงงาน/โกดัง",
    "Mini Factory": "โรงงาน/โกดัง",
    
    # 8. หมวดอพาร์ทเมนท์ / หอพัก
    "อพาร์ทเม้นท์": "อพาร์ทเมนท์",
    "อพาร์ตเมนต์": "อพาร์ทเมนท์",
    "อพาตเมนต์": "อพาร์ทเมนท์",
    "หอพัก": "อพาร์ทเมนท์",
    "หอพัก/อพาร์ทเมนท์": "อพาร์ทเมนท์",
    "อพาร์ทเม้นท์/หอพัก": "อพาร์ทเมนท์",
    "แฟลต": "อพาร์ทเมนท์",
    "อาคารพักอาศัย": "อพาร์ทเมนท์",
    "Apartment": "อพาร์ทเมนท์",
    "Dormitory": "อพาร์ทเมนท์",
    "Flat": "อพาร์ทเมนท์",
    
    # 9. หมวดอาคารพาณิชย์ / ตึกแถว / ร้านค้า
    "ตึกแถว": "อาคารพาณิชย์",
    "ห้องแถว": "อาคารพาณิชย์",
    "ร้านค้า": "อาคารพาณิชย์",
    "ร้านอาหาร": "อาคารพาณิชย์",
    "ตลาดสด": "อาคารพาณิชย์",
    "ศูนย์จำหน่ายสินค้า": "อาคารพาณิชย์",
    "ห้างสรรพสินค้า": "อาคารพาณิชย์",
    "โชว์รูม": "อาคารพาณิชย์",
    "Commercial Property": "อาคารพาณิชย์",
    "Commercial Space": "อาคารพาณิชย์",
    "Commercial Building": "อาคารพาณิชย์",
    "Shophouse": "อาคารพาณิชย์",
    "Shop House": "อาคารพาณิชย์",
    "Retail": "อาคารพาณิชย์",
    "Showroom": "อาคารพาณิชย์",
    
    # 10. หมวดสำนักงาน
    "สำนักงาน": "อาคารสำนักงาน",
    "โฮมออฟฟิศ": "อาคารสำนักงาน",
    "อาคารที่ทำการสาขา": "อาคารสำนักงาน",
    "ห้องชุดสำนักงาน": "ห้องชุดพาณิชยกรรม/สำนักงาน",
    "ห้องชุดพาณิชยกรรม": "ห้องชุดพาณิชยกรรม/สำนักงาน",
    "Office": "อาคารสำนักงาน",
    "Office Building": "อาคารสำนักงาน",
    "Home Office": "อาคารสำนักงาน",
    
    # 11. หมวดโรงแรม / รีสอร์ท
    "Hotel Building": "โรงแรม/รีสอร์ท",
    "โรงแรม": "โรงแรม/รีสอร์ท",
    "รีสอร์ท": "โรงแรม/รีสอร์ท",
    "Hotel": "โรงแรม/รีสอร์ท",
    "Resort": "โรงแรม/รีสอร์ท",
    
    # 12. หมวดสังหาริมทรัพย์ & อื่นๆ
    "เครื่องจักร": "สังหาริมทรัพย์",
    "บัตรสมาชิกสนามกอล์ฟ": "สังหาริมทรัพย์",
    "ส่วนโล่งหลังคาคลุม": "อื่นๆ",
    "ฟาร์มเลี้ยงสัตว์": "ฟาร์ม",
    "สถานีบริการน้ำมัน": "ปั๊มน้ำมัน",
    "ศูนย์บริการ/โชว์รูม/ปั้มน้ำมัน": "ปั๊มน้ำมัน",
    "โรงภาพยนต์": "อื่นๆ",
    "สวนน้ำ": "อื่นๆ",
    "โรงพยาบาล": "อื่นๆ",
    "อาคารจอดรถ": "อื่นๆ",
    "บ้านพักคนงาน": "อื่นๆ",
    "อาคาร": "อื่นๆ",
    "Public Service": "อื่นๆ",
    "โครงการที่พักอาศัย/พาณิชยกรรม": "อื่นๆ",
    "อสังหาริมทรัพย์อื่นๆ": "อื่นๆ",
}

SALE_TYPE_MAPPING = {
    # ขายทอดตลาด (ปลอดจำนอง)
    'ปลอดการจำนอง': 'ขายทอดตลาด (ปลอดจำนอง)',
    'ไม่มีภาระจำนอง': 'ขายทอดตลาด (ปลอดจำนอง)',
    'ปลอดภาระผูกพัน': 'ขายทอดตลาด (ปลอดจำนอง)',
    'ไม่มีภาระจำนำ': 'ขายทอดตลาด (ปลอดจำนอง)',
    'ประมูล': 'ขายทอดตลาด (ปลอดจำนอง)',
    
    # ขายทอดตลาด (จำนองติดไป)
    'การจำนองติดไป': 'ขายทอดตลาด (จำนองติดไป)',
    'การจำนำติดไป': 'ขายทอดตลาด (จำนองติดไป)',
    
    # ขายตรง
    'ซื้อตรง': 'ขาย',
    'ทรัพย์ธนาคาร': 'ขาย',
    'ทรัพย์โปรโมชั่นราคาพิเศษ': 'ขาย',
    'ทรัพย์โปรโมชันราคาพิเศษ': 'ขาย',
    'โปรโมชั่น': 'ขาย',
    'โปรโมชัน': 'ขาย',
    'ทรัพย์ฝากขาย': 'ขาย',
    'ฝากขาย': 'ขาย',
    'ขายดาวน์': 'ขาย',
    'ขาย/เช่า': 'ขาย',
}

def make_clean_dropdown_label(row, show_company=True):
    """Creates clean, highly informative dropdown labels with company, property type, name/project, code, location, and price."""
    co = str(row.get('บริษัท', '')).strip()
    title = str(row.get('ชื่อประกาศ', '')).strip()
    proj = str(row.get('ชื่อโครงการ', '')).strip()
    code = str(row.get('รหัสทรัพย์', '')).strip()
    ptype = str(row.get('ประเภททรัพย์', '')).strip()
    prov = str(row.get('จังหวัด', '')).strip()
    dist = str(row.get('อำเภอ', '')).strip()
    price = row.get('ราคา', 0)
    
    try:
        f_price = float(price)
        price_str = f"฿{f_price:,.0f}" if f_price > 0 else "ไม่ระบุราคา"
    except (ValueError, TypeError):
        price_str = "ไม่ระบุราคา"
        
    # Pick the best descriptive name
    name = title
    if (not name or name in ['SAM', 'BAM', 'ไม่มีชื่อ', 'ทรัพย์สิน NPA', '-', 'nan']) and proj and proj not in ['nan', 'None', '-']:
        name = proj
    elif proj and proj not in ['nan', 'None', '-', ''] and proj.lower() not in title.lower() and len(name) < 25:
        name = f"{name} ({proj})"
        
    if len(name) > 40:
        name = name[:38] + "..."
        
    loc_parts = []
    if dist and dist not in ['nan', 'None', '-']:
        loc_parts.append(dist)
    if prov and prov not in ['nan', 'None', '-']:
        loc_parts.append(prov)
    loc_joined = ', '.join(loc_parts)
    loc_str = f" [{loc_joined}]" if loc_parts else ""
    
    code_str = f" ({code})" if code and code not in ['nan', 'None', '-'] else ""
    ptype_str = f"{ptype}: " if ptype and ptype not in ['nan', 'None', '-'] else ""
    prefix = f"[{co}] " if show_company and co and co not in ['nan', 'None', '-'] else ""
    
    return f"{prefix}{ptype_str}{name}{code_str}{loc_str} - {price_str}"
