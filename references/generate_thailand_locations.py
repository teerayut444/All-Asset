import urllib.request
import json
import os
import pandas as pd

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. Standard 6-Region Geography Mapping for 77 Provinces
REGION_MAPPING = {
    # ภาคเหนือ (North) - 9 จังหวัด
    "เชียงใหม่": "ภาคเหนือ", "เชียงราย": "ภาคเหนือ", "น่าน": "ภาคเหนือ",
    "พะเยา": "ภาคเหนือ", "แพร่": "ภาคเหนือ", "แม่ฮ่องสอน": "ภาคเหนือ",
    "ลำปาง": "ภาคเหนือ", "ลำพูน": "ภาคเหนือ", "อุตรดิตถ์": "ภาคเหนือ",

    # ภาคกลาง (Central) - 22 จังหวัด
    "กรุงเทพมหานคร": "ภาคกลาง", "กำแพงเพชร": "ภาคกลาง", "ชัยนาท": "ภาคกลาง",
    "นครนายก": "ภาคกลาง", "นครปฐม": "ภาคกลาง", "นครสวรรค์": "ภาคกลาง",
    "นนทบุรี": "ภาคกลาง", "ปทุมธานี": "ภาคกลาง", "พระนครศรีอยุธยา": "ภาคกลาง",
    "พิจิตร": "ภาคกลาง", "พิษณุโลก": "ภาคกลาง", "เพชรบูรณ์": "ภาคกลาง",
    "ลพบุรี": "ภาคกลาง", "สมุทรปราการ": "ภาคกลาง", "สมุทรสงคราม": "ภาคกลาง",
    "สมุทรสาคร": "ภาคกลาง", "สระบุรี": "ภาคกลาง", "สิงห์บุรี": "ภาคกลาง",
    "สุโขทัย": "ภาคกลาง", "สุพรรณบุรี": "ภาคกลาง", "อ่างทอง": "ภาคกลาง", "อุทัยธานี": "ภาคกลาง",

    # ภาคตะวันออกเฉียงเหนือ (Northeast) - 20 จังหวัด
    "กาฬสินธุ์": "ภาคตะวันออกเฉียงเหนือ", "ขอนแก่น": "ภาคตะวันออกเฉียงเหนือ",
    "ชัยภูมิ": "ภาคตะวันออกเฉียงเหนือ", "นครพนม": "ภาคตะวันออกเฉียงเหนือ",
    "นครราชสีมา": "ภาคตะวันออกเฉียงเหนือ", "บึงกาฬ": "ภาคตะวันออกเฉียงเหนือ",
    "บุรีรัมย์": "ภาคตะวันออกเฉียงเหนือ", "มหาสารคาม": "ภาคตะวันออกเฉียงเหนือ",
    "มุกดาหาร": "ภาคตะวันออกเฉียงเหนือ", "ยโสธร": "ภาคตะวันออกเฉียงเหนือ",
    "ร้อยเอ็ด": "ภาคตะวันออกเฉียงเหนือ", "เลย": "ภาคตะวันออกเฉียงเหนือ",
    "ศรีสะเกษ": "ภาคตะวันออกเฉียงเหนือ", "สกลนคร": "ภาคตะวันออกเฉียงเหนือ",
    "สุรินทร์": "ภาคตะวันออกเฉียงเหนือ", "หนองคาย": "ภาคตะวันออกเฉียงเหนือ",
    "หนองบัวลำภู": "ภาคตะวันออกเฉียงเหนือ", "อำนาจเจริญ": "ภาคตะวันออกเฉียงเหนือ",
    "อุดรธานี": "ภาคตะวันออกเฉียงเหนือ", "อุบลราชธานี": "ภาคตะวันออกเฉียงเหนือ",

    # ภาคตะวันออก (East) - 7 จังหวัด
    "จันทบุรี": "ภาคตะวันออก", "ฉะเชิงเทรา": "ภาคตะวันออก", "ชลบุรี": "ภาคตะวันออก",
    "ตราด": "ภาคตะวันออก", "ปราจีนบุรี": "ภาคตะวันออก", "ระยอง": "ภาคตะวันออก",
    "สระแก้ว": "ภาคตะวันออก",

    # ภาคตะวันตก (West) - 5 จังหวัด
    "กาญจนบุรี": "ภาคตะวันตก", "ตาก": "ภาคตะวันตก", "ประจวบคีรีขันธ์": "ภาคตะวันตก",
    "เพชรบุรี": "ภาคตะวันตก", "ราชบุรี": "ภาคตะวันตก",

    # ภาคใต้ (South) - 14 จังหวัด
    "กระบี่": "ภาคใต้", "ชุมพร": "ภาคใต้", "ตรัง": "ภาคใต้",
    "นครศรีธรรมราช": "ภาคใต้", "นราธิวาส": "ภาคใต้", "ปัตตานี": "ภาคใต้",
    "พังงา": "ภาคใต้", "พัทลุง": "ภาคใต้", "ภูเก็ต": "ภาคใต้",
    "ยะลา": "ภาคใต้", "ระนอง": "ภาคใต้", "สงขลา": "ภาคใต้",
    "สตูล": "ภาคใต้", "สุราษฎร์ธานี": "ภาคใต้"
}

def fetch_data():
    base = 'https://raw.githubusercontent.com/thailand-geography-data/thailand-geography-json/main/src/'
    urls = {
        'provinces': base + 'provinces.json',
        'districts': base + 'districts.json',
        'subdistricts': base + 'subdistricts.json',
        'geography': base + 'geography.json'
    }
    
    data = {}
    for key, url in urls.items():
        print(f"Downloading {key}...")
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data[key] = json.loads(resp.read().decode('utf-8'))
    return data

def main():
    raw = fetch_data()
    geo_list = raw['geography']
    provinces_list = raw['provinces']
    districts_list = raw['districts']
    subdistricts_list = raw['subdistricts']
    
    rows = []
    for item in geo_list:
        prov_th = item.get("provinceNameTh", "").strip()
        region = REGION_MAPPING.get(prov_th, "ภาคกลาง")
        
        # Clean postal code as 5-digit zero-padded string
        p_code = item.get("postalCode", "")
        p_code_str = f"{int(p_code):05d}" if p_code and str(p_code).isdigit() else str(p_code)
        
        rows.append({
            "ลำดับ": item.get("id"),
            "ภูมิภาค": region,
            "รหัสจังหวัด": item.get("provinceCode"),
            "จังหวัด (ไทย)": prov_th,
            "จังหวัด (อังกฤษ)": item.get("provinceNameEn", "").strip(),
            "รหัสอำเภอ": item.get("districtCode"),
            "อำเภอ/เขต (ไทย)": item.get("districtNameTh", "").strip(),
            "อำเภอ/เขต (อังกฤษ)": item.get("districtNameEn", "").strip(),
            "รหัสตำบล": item.get("subdistrictCode"),
            "ตำบล/แขวง (ไทย)": item.get("subdistrictNameTh", "").strip(),
            "ตำบล/แขวง (อังกฤษ)": item.get("subdistrictNameEn", "").strip(),
            "รหัสไปรษณีย์": p_code_str
        })
        
    df_all = pd.DataFrame(rows)
    
    # Summary DataFrames
    df_provinces = pd.DataFrame([{
        "รหัสจังหวัด": p.get("provinceCode"),
        "ภูมิภาค": REGION_MAPPING.get(p.get("provinceNameTh", "").strip(), "ภาคกลาง"),
        "จังหวัด (ไทย)": p.get("provinceNameTh", "").strip(),
        "จังหวัด (อังกฤษ)": p.get("provinceNameEn", "").strip()
    } for p in provinces_list]).sort_values("รหัสจังหวัด")
    
    df_districts = pd.DataFrame([{
        "รหัสอำเภอ": d.get("districtCode"),
        "รหัสจังหวัด": d.get("provinceCode"),
        "อำเภอ/เขต (ไทย)": d.get("districtNameTh", "").strip(),
        "อำเภอ/เขต (อังกฤษ)": d.get("districtNameEn", "").strip(),
        "รหัสไปรษณีย์": f"{int(d.get('postalCode')):05d}" if d.get('postalCode') and str(d.get('postalCode')).isdigit() else str(d.get('postalCode', ''))
    } for d in districts_list]).sort_values("รหัสอำเภอ")
    
    # Output file paths
    csv_path = os.path.join(CURRENT_DIR, "thailand_provinces_districts_subdistricts.csv")
    xlsx_path = os.path.join(CURRENT_DIR, "thailand_provinces_districts_subdistricts.xlsx")
    json_path = os.path.join(CURRENT_DIR, "thailand_provinces_districts_subdistricts.json")
    
    # 1. Export CSV (utf-8-sig for Excel compatibility)
    df_all.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"Exported CSV: {csv_path} ({len(df_all):,} records)")
    
    # 2. Export JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print(f"Exported JSON: {json_path}")
    
    # 3. Export Excel with Multi-sheets
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df_all.to_excel(writer, sheet_name="ข้อมูลทั้งหมด (All)", index=False)
        df_provinces.to_excel(writer, sheet_name="จังหวัด (Provinces)", index=False)
        df_districts.to_excel(writer, sheet_name="อำเภอ (Districts)", index=False)
    print(f"Exported Excel: {xlsx_path}")

if __name__ == "__main__":
    main()
