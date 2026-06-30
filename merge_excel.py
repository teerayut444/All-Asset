import pandas as pd
import numpy as np
from pathlib import Path
import os
import time

def merge_all_excel():
    print("=== เริ่มการรวมไฟล์ Excel ===")
    
    # กำหนดพาธไฟล์ต้นทาง
    base_dir = Path(r"c:\Users\Teerayut.N\.vscode\extensions")
    files = {
        "Baania": base_dir / "Baania NPA" / "baania_listings.xlsx",
        "BAM": base_dir / "BAM NPA" / "BAM NPA.xlsx",
        "SAM": base_dir / "SAM NPA" / "SAM NPA.xlsx",
        "ZmyHome": base_dir / "ZmyHome NPA" / "ZmyHome NPA.xlsx",
    }
    
    # กำหนดพาธไฟล์ปลายทาง
    dest_dir = base_dir / "All Asset Dashboard"
    dest_dir.mkdir(parents=True, exist_ok=True)
    output_file = dest_dir / "all_assets.xlsx"
    
    # โหลดและแปลงข้อมูล
    dfs = []
    
    # ลำดับคอลัมน์มาตรฐาน (คอลัมน์เดิม 19 ช่อง + เพิ่ม บริษัท เป็นคอลัมน์แรก)
    standard_columns = [
        "บริษัท", "ID", "รหัสทรัพย์", "ชื่อโครงการ", "ประเภททรัพย์", "ประเภทการขาย", "ราคา",
        "ตำบล", "อำเภอ", "จังหวัด", "ละติจูด", "ลองจิจูด", "ชื่อประกาศ", "ลิงก์",
        "พื้นที่ (ไร่-งาน-วา)", "พื้นที่ใช้สอย (ตร.ม.)", "วันที่ดึงข้อมูล", "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ"
    ]
    
    for company, path in files.items():
        if not path.exists():
            print(f"[Warning] ไม่พบไฟล์ Excel ของ {company} ที่ตำแหน่ง: {path}")
            continue
            
        print(f"กำลังโหลดไฟล์ {company} ({path.name})...")
        try:
            # โหลดไฟล์ (โหลดทุกคอลัมน์เป็น String เพื่อรักษาฟอร์แมตเดิม แล้วค่อยแปลงภายหลัง)
            df = pd.read_excel(path, dtype=str)
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')] # ลบคอลัมน์ไม่มีชื่อ
            
            # ปรับจูนโครงสร้างคอลัมน์สำหรับ ZmyHome กรณีที่หัวตารางเป็นเวอร์ชันอื่น
            if company == "ZmyHome":
                rename_map = {
                    "พื้นที่ดิน": "พื้นที่ (ไร่-งาน-วา)",
                    "พื้นที่ (ตร.ม.)": "พื้นที่ใช้สอย (ตร.ม.)",
                    "วันที่ดึง": "วันที่ดึงข้อมูล"
                }
                df = df.rename(columns=rename_map)
                if ("รหัสทรัพย์" not in df.columns or df["รหัสทรัพย์"].isna().all()) and "ID" in df.columns:
                    df["รหัสทรัพย์"] = df["ID"]
                
                # โหลดชื่อประกาศจาก temp_title_map.json มาแมปป้อนลงในช่อง ชื่อประกาศ
                json_path = base_dir / "ZmyHome NPA" / "temp_title_map.json"
                if json_path.exists():
                    import json
                    print(f"  -> พบไฟล์ temp_title_map.json ของ ZmyHome กำลังดึงข้อมูลชื่อประกาศ...")
                    try:
                        with open(json_path, "r", encoding="utf-8") as f:
                            title_map = json.load(f)
                        
                        # สร้างฟังก์ชันแมปชื่อประกาศ
                        def map_title(row):
                            # ลำดับที่ 1: ใช้ ชื่อโครงการ เป็น ชื่อประกาศ เสมอตามความต้องการของลูกค้า
                            proj_name = str(row.get("ชื่อโครงการ", "")).strip()
                            if proj_name and proj_name.lower() != "nan" and proj_name != "" and proj_name != "-":
                                return proj_name
                                
                            # ลำดับที่ 2: หากไม่มีชื่อโครงการ ค่อยดึงจากชื่อประกาศเดิม (โฆษณา)
                            orig = str(row.get("ชื่อประกาศ", "")).strip()
                            if orig and orig.lower() != "nan" and orig != "":
                                return orig
                            
                            # ลำดับที่ 3: ดึงข้อมูลจาก temp_title_map.json
                            ref_id = str(row.get("รหัสทรัพย์", "")).strip()
                            if ref_id in title_map and title_map[ref_id]:
                                return title_map[ref_id]
                            
                            ref_id_id = str(row.get("ID", "")).strip()
                            if ref_id_id in title_map and title_map[ref_id_id]:
                                return title_map[ref_id_id]
                                
                            # ลำดับที่ 4: Fallback สุดท้ายด้วย ประเภททรัพย์ + ทำเลที่ตั้ง
                            prop_type = str(row.get("ประเภททรัพย์", "ทรัพย์สิน")).strip()
                            subdistrict = str(row.get("ตำบล", "")).strip()
                            district = str(row.get("อำเภอ", "")).strip()
                            province = str(row.get("จังหวัด", "")).strip()
                            
                            loc_parts = []
                            if subdistrict:
                                loc_parts.append(subdistrict)
                            if district:
                                loc_parts.append(district)
                            if province and province != "ไม่ระบุ":
                                loc_parts.append(province)
                                
                            loc_str = " ".join(loc_parts)
                            if loc_str:
                                return f"{prop_type} ทำเล {loc_str}"
                            return f"{prop_type} (ZmyHome)"
                            
                        df["ชื่อประกาศ"] = df.apply(map_title, axis=1)
                        filled_count = (df["ชื่อประกาศ"].fillna("").astype(str).str.strip() != "").sum()
                        print(f"  -> แมปชื่อประกาศสำเร็จ (รวม fallback): {filled_count} รายการ")
                    except Exception as json_err:
                        print(f"  [Warning] ไม่สามารถโหลดไฟล์แมปชื่อประกาศได้: {json_err}")
            
            # ลบค่า $undefined หรือ undefined ที่อาจติดมาจาก scraper
            df = df.replace(["$undefined", "undefined", "nan", "NaN", "NAN"], np.nan)
            
            # ใส่คอลัมน์แหล่งที่มาข้อมูล
            df["บริษัท"] = company
            
            # เติมคอลัมน์ที่หายไปให้ครบตามมาตรฐาน
            for col in standard_columns:
                if col not in df.columns:
                    df[col] = np.nan
                    
            # เรียงคอลัมน์ตามลำดับมาตรฐาน
            df = df[standard_columns]
            dfs.append(df)
            print(f"-> โหลดสำเร็จ: {len(df)} แถว")
            
        except Exception as e:
            print(f"[Error] เกิดข้อผิดพลาดขณะโหลดไฟล์ของ {company}: {e}")
            
    if not dfs:
        print("[Error] ไม่พบไฟล์ข้อมูลใดๆ สำหรับนำมารวมกัน!")
        return False
        
    print("กำลังรวมข้อมูลและปรับฟอร์แมต...")
    combined_df = pd.concat(dfs, ignore_index=True)
    
    # แปลงคอลัมน์ตัวเลข
    combined_df["ราคา"] = pd.to_numeric(combined_df["ราคา"], errors="coerce")
    combined_df["ละติจูด"] = pd.to_numeric(combined_df["ละติจูด"], errors="coerce")
    combined_df["ลองจิจูด"] = pd.to_numeric(combined_df["ลองจิจูด"], errors="coerce")
    
    # เคลียร์และทำความสะอาดช่องข้อความทั่วไป
    text_cols = ["รหัสทรัพย์", "ชื่อโครงการ", "ประเภททรัพย์", "ประเภทการขาย", "ตำบล", "อำเภอ", "จังหวัด", "ชื่อประกาศ", "พื้นที่ (ไร่-งาน-วา)"]
    for col in text_cols:
        combined_df[col] = combined_df[col].fillna("").astype(str).str.strip()

    # ทำความสะอาดชื่อจังหวัดที่พิมพ์ผิด หรือมีการ Shift คอลัมน์เอาอำเภอ/ตำบลมาใส่ช่องจังหวัด
    THAI_PROVINCES = {
        "กรุงเทพมหานคร", "กระบี่", "กาญจนบุรี", "กาฬสินธุ์", "กำแพงเพชร", "ขอนแก่น", "จันทบุรี", "ฉะเชิงเทรา", "ชลบุรี", "ชัยนาท", 
        "ชัยภูมิ", "ชุมพร", "เชียงราย", "เชียงใหม่", "ตรัง", "ตราด", "ตาก", "นครนายก", "นครปฐม", "นครพนม", "นครราชสีมา", 
        "นครศรีธรรมราช", "นครสวรรค์", "นนทบุรี", "นราธิวาส", "น่าน", "บึงกาฬ", "บุรีรัมย์", "ปทุมธานี", "ประจวบคีรีขันธ์", 
        "ปราจีนบุรี", "ปัตตานี", "พระนครศรีอยุธยา", "พะเยา", "พังงา", "พัทลุง", "พิจิตร", "พิษณุโลก", "เพชรบุรี", "เพชรบูรณ์", 
        "แพร่", "ภูเก็ต", "มหาสารคาม", "มุกดาหาร", "แม่ฮ่องสอน", "ยโสธร", "ยะลา", "ร้อยเอ็ด", "ระนอง", "ระยอง", 
        "ราชบุรี", "ลพบุรี", "ลำปาง", "ลำพูน", "เลย", "ศรีสะเกษ", "สกลนคร", "สงขลา", "สตูล", "สมุทรปราการ", "สมุทรสงคราม", 
        "สมุทรสาคร", "สระแก้ว", "สระบุรี", "สิงห์บุรี", "สุโขทัย", "สุพรรณบุรี", "สุราษฎร์ธานี", "สุรินทร์", "หนองคาย", 
        "หนองบัวลำภู", "อ่างทอง", "อุดรธานี", "อุทัยธานี", "อุตรดิตถ์", "อุบลราชธานี", "อำนาจเจริญ"
    }
    
    PROVINCE_MAPPING = {
        "PATHUM THANI": "ปทุมธานี",
        "NAKHON SAWAN": "นครสวรรค์",
        "กรุงเทพ": "กรุงเทพมหานคร",
        "กรุงเทพฯ": "กรุงเทพมหานคร",
        "ปทุม": "ปทุมธานี",
        "อยุธยา": "พระนครศรีอยุธยา",
        "โคราช": "นครราชสีมา",
    }
    
    DISTRICT_TO_PROVINCE = {
        "บางบัวทอง": "นนทบุรี", "บางใหญ่": "นนทบุรี", "ปากเกร็ด": "นนทบุรี", "เมืองนนทบุรี": "นนทบุรี", 
        "บางกรวย": "นนทบุรี", "บางศรีเมือง": "นนทบุรี", "ไทรม้า": "นนทบุรี", "บางรักพัฒนา": "นนทบุรี",
        "บางรักน้อย": "นนทบุรี", "เสาธงหิน": "นนทบุรี", "ท่าอิฐ": "นนทบุรี", "คลองเกลือ": "นนทบุรี",
        "ธัญบุรี": "ปทุมธานี", "คลองหลวง": "ปทุมธานี", "ลำลูกกา": "ปทุมธานี", "สามโคก": "ปทุมธานี", 
        "ลาดหลุมแก้ว": "ปทุมธานี", "เมืองปทุมธานี": "ปทุมธานี", "คลองสอง": "ปทุมธานี", "คลองหนึ่ง": "ปทุมธานี",
        "คลองสาม": "ปทุมธานี", "คลองสี่": "ปทุมธานี", "คลองห้า": "ปทุมธานี", "คลองหก": "ปทุมธานี",
        "ประชาธิปัตย์": "ปทุมธานี", "คูคต": "ปทุมธานี", "ลาดสวาย": "ปทุมธานี", "บึงยี่โถ": "ปทุมธานี",
        "บางพลี": "สมุทรปราการ", "พระประแดง": "สมุทรปราการ", "บางบ่อ": "สมุทรปราการ", "บางเสาธง": "สมุทรปราการ", 
        "พระสมุทรเจดีย์": "สมุทรปราการ", "เมืองสมุทรปราการ": "สมุทรปราการ", "ราชาเทวะ": "สมุทรปราการ",
        "บางพลีใหญ่": "สมุทรปราการ", "สำโรง": "สมุทรปราการ", "สำโรงเหนือ": "สมุทรปราการ", "บางเมือง": "สมุทรปราการ",
        "ลาดพร้าว": "กรุงเทพมหานคร", "บางกะปิ": "กรุงเทพมหานคร", "มีนบุรี": "กรุงเทพมหานคร", "ประเวศ": "กรุงเทพมหานคร", 
        "จอมทอง": "กรุงเทพมหานคร", "สายไหม": "กรุงเทพมหานคร", "ทวีวัฒนา": "กรุงเทพมหานคร", "สวนหลวง": "กรุงเทพมหานคร", 
        "ห้วยขวาง": "กรุงเทพมหานคร", "คลองสามวา": "กรุงเทพมหานคร", "คันนายาว": "กรุงเทพมหานคร", "ตลิ่งชัน": "กรุงเทพมหานคร", 
        "บางแค": "กรุงเทพมหานคร", "บางบอน": "กรุงเทพมหานคร", "บางนา": "กรุงเทพมหานคร", "ลาดกระบัง": "กรุงเทพมหานคร", 
        "บึงกุ่ม": "กรุงเทพมหานคร", "สะพานสูง": "กรุงเทพมหานคร", "ดอนเมือง": "กรุงเทพมหานคร", "หลักสี่": "กรุงเทพมหานคร", 
        "พญาไท": "กรุงเทพมหานคร", "ดินแดง": "กรุงเทพมหานคร", "ปทุมวัน": "กรุงเทพมหานคร", "คลองถนน": "กรุงเทพมหานคร",
        "จรเข้บัว": "กรุงเทพมหานคร", "คลองเจ้าคุณสิงห์": "กรุงเทพมหานคร", "บางมด": "กรุงเทพมหานคร", "สีกัน": "กรุงเทพมหานคร",
        "ทุ่งสองห้อง": "กรุงเทพมหานคร", "ทุ่งครุ": "กรุงเทพมหานคร", "บางนาเหนือ": "กรุงเทพมหานคร", "บางนาใต้": "กรุงเทพมหานคร",
        "บางบอนเหนือ": "กรุงเทพมหานคร", "หัวหมาก": "กรุงเทพมหานคร", "แสมดำ": "กรุงเทพมหานคร", "คลองเตย": "กรุงเทพมหานคร",
        "ศรีราชา": "ชลบุรี", "บางละมุง": "ชลบุรี", "เมืองชลบุรี": "ชลบุรี", "พานทอง": "ชลบุรี", 
        "พนัสนิคม": "ชลบุรี", "บ้านบึง": "ชลบุรี", "สัตหีบ": "ชลบุรี", "พัทยา": "ชลบุรี",
        "หนองปรือ": "ชลบุรี", "ตะเคียนเตี้ย": "ชลบุรี", "ทุ่งสุขลา": "ชลบุรี", "แสนสุข": "ชลบุรี",
        "สามพราน": "นครปฐม", "นครชัยศรี": "นครปฐม", "พุทธมณฑล": "นครปฐม", "เมืองนครปฐม": "นครปฐม",
        "ศาลายา": "นครปฐม", "กระทุ่มล้ม": "นครปฐม", "อ้อมใหญ่": "นครปฐม", "ยายชา": "นครปฐม",
        "กระทุ่มแบน": "สมุทรสาคร", "เมืองสมุทรสาคร": "สมุทรสาคร", "บ้านแพ้ว": "สมุทรสาคร", "อ้อมน้อย": "สมุทรสาคร",
        "มหาชัย": "สมุทรสาคร", "ท่าทราย": "สมุทรสาคร", "พันท้ายนรสิงห์": "สมุทรสาคร", "บางโทรัด": "สมุทรสาคร",
        "ชะอำ": "เพชรบุรี", "หัวหิน": "ประจวบคีรีขันธ์", "ปราณบุรี": "ประจวบคีรีขันธ์", "ทับสะแก": "ประจวบคีรีขันธ์",
    }

    def clean_prov(row):
        p = str(row["จังหวัด"]).strip()
        d = str(row["อำเภอ"]).strip()
        s = str(row["ตำบล"]).strip()
        
        # Mapping common terms
        if p in PROVINCE_MAPPING:
            p = PROVINCE_MAPPING[p]
        if p.startswith("จ."):
            p = p[2:].strip()
        elif p.startswith("จังหวัด"):
            p = p[7:].strip()
            
        # Check misplaced district/subdistrict in province column
        if p in DISTRICT_TO_PROVINCE:
            p = DISTRICT_TO_PROVINCE[p]
        elif d in DISTRICT_TO_PROVINCE:
            p = DISTRICT_TO_PROVINCE[d]
        elif s in DISTRICT_TO_PROVINCE:
            p = DISTRICT_TO_PROVINCE[s]
            
        if p in THAI_PROVINCES:
            return p
        return "ไม่ระบุ"

    # Apply geographic cleaning
    combined_df["จังหวัด"] = combined_df.apply(clean_prov, axis=1)

    # ทำความสะอาดและจัดกลุ่มประเภททรัพย์
    def clean_asset_type(row):
        val = str(row.get("ประเภททรัพย์", "")).strip()
        
        mapping = {
            "บ้าน": "บ้านเดี่ยว",
            "คอนโดมิเนียม": "คอนโด",
            "ห้องชุดพักอาศัย": "คอนโด",
            "ทาวน์เฮ้าส์": "ทาวน์เฮ้าส์",
            "ทาวน์โฮม": "ทาวน์เฮ้าส์",
            "ที่ดิน": "ที่ดินเปล่า",
            "โกดัง / โรงงาน": "โรงงาน/โกดัง",
            "โกดัง/โรงงาน": "โรงงาน/โกดัง",
            "โรงงาน": "โรงงาน/โกดัง",
            "อพาร์ทเม้นท์": "อพาร์ตเมนต์",
            "อพาร์ทเมนท์": "อพาร์ตเมนต์",
            "อพาตเมนต์": "อพาร์ตเมนต์",
            "สำนักงาน": "อาคารสำนักงาน",
            "ห้องชุดสำนักงาน": "อาคารสำนักงาน",
            "ห้องชุดพาณิชยกรรม": "อาคารพาณิชย์",
            "โรงแรม/รีสอร์ท": "โรงแรม",
        }
        
        if val in mapping:
            return mapping[val]
            
        if val == "บ้านเดี่ยว/ทาวน์เฮาส์" or val == "บ้านเดี่ยว/ทาวน์เฮ้าส์":
            proj = str(row.get("ชื่อโครงการ", "")).lower()
            t_words = ['ทาวน์', 'town', 'วิลล์', 'ville', 'พลีโน่', 'pleno', 'พฤกษาวิลล์', 'เบล็ส ทาวน์', 'เพล็กซ์', 'ทาวน์โฮม', 'ทาวน์เฮ้าส์', 'ทาวน์เฮาส์', 'ตึกแถว', 'shophouse']
            if any(w in proj for w in t_words):
                return 'ทาวน์เฮ้าส์'
            
            d_words = ['บ้านเดี่ยว', 'เดอะ แพลนท์', 'the plant', 'ลดาวัลย์', 'มัณฑนา', 'เศรษฐสิริ', 'เพอร์เฟค', 'ชลลดา', 'ภัสสร', 'บุราสิริ', 'นันทวัน', 'วิลเลจ', 'village', 'neo', 'นีโอ', 'เฮ้าส์', 'house', 'บ้านแฝด']
            if any(w in proj for w in d_words):
                return 'บ้านเดี่ยว'
                
            area_str = str(row.get("พื้นที่ (ไร่-งาน-วา)", "")).strip()
            if area_str and area_str != 'nan':
                try:
                    parts = area_str.split('-')
                    if len(parts) == 3:
                        total_wah = (float(parts[0] or 0) * 400) + (float(parts[1] or 0) * 100) + float(parts[2] or 0)
                        if total_wah > 0:
                            return 'บ้านเดี่ยว' if total_wah >= 40 else 'ทาวน์เฮ้าส์'
                except:
                    pass
            return 'บ้านเดี่ยว'
            
        return val

    combined_df["ประเภททรัพย์"] = combined_df.apply(clean_asset_type, axis=1)

    # คัดแยกค่าว่างให้สวยงาม
    combined_df["ชื่อโครงการ"] = combined_df["ชื่อโครงการ"].replace("", np.nan)
    
    # Retry loop for saving
    max_save_retries = 3
    for attempt in range(max_save_retries):
        try:
            print(f"กำลังบันทึกไฟล์รวมไปที่: {output_file}")
            combined_df.to_excel(output_file, index=False, engine="openpyxl")
            print(f"=== บันทึกสำเร็จ! รวมแถวทั้งหมด: {len(combined_df)} แถว ===")
            return True
        except PermissionError as pe:
            if attempt < max_save_retries - 1:
                print(f"[Warning] ไฟล์ {output_file.name} ถูกล็อกอยู่ (อาจเปิดอยู่ใน Excel) จะลองใหม่ใน 5 วินาที... (พยายามครั้งที่ {attempt+1}/{max_save_retries})")
                time.sleep(5)
            else:
                alt_output = output_file.with_name("all_assets_TEMP.xlsx")
                print(f"[Error] ไม่สามารถเขียนทับ {output_file.name} ได้เนื่องจากถูกล็อก บันทึกข้อมูลสำรองไว้ที่ {alt_output.name} แทน: {pe}")
                try:
                    combined_df.to_excel(alt_output, index=False, engine="openpyxl")
                    print(f"=== บันทึกไฟล์สำรองสำเร็จ! จำนวน: {len(combined_df)} แถว ===")
                    return True
                except Exception as alt_e:
                    print(f"[Error] ไม่สามารถบันทึกไฟล์สำรองได้เช่นกัน: {alt_e}")
                    return False
        except Exception as e:
            print(f"[Error] ไม่สามารถบันทึกไฟล์ Excel ได้: {e}")
            return False

if __name__ == "__main__":
    merge_all_excel()
