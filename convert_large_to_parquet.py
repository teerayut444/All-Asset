import pandas as pd
import os
import time

def optimize_and_convert(input_file="all_assets.xlsx", output_file="all_assets.parquet"):
    print(f"=== Starting Optimization & Conversion ===")
    print(f"Target Input: {input_file}")
    
    start_time = time.time()
    
    if not os.path.exists(input_file) and not os.path.exists(output_file):
        print(f"Error: {input_file} not found!")
        return
        
    if os.path.exists(input_file):
        size_raw = os.path.getsize(input_file) / (1024 * 1024)
        print(f"Raw Input File Size: {size_raw:.2f} MB")
        if input_file.endswith(".csv"):
            df = pd.read_csv(input_file, low_memory=False)
        else:
            df = pd.read_excel(input_file)
    else:
        print("Loading existing parquet to re-optimize...")
        df = pd.read_parquet(output_file)

    total_rows = len(df)
    print(f"Total Rows Loaded: {total_rows:,} rows")
    
    # Category Casting for Repetitive Text Columns
    cat_cols = ['บริษัท', 'ประเภททรัพย์', 'ประเภทการขาย', 'จังหวัด', 'อำเภอ', 'ห้องนอน', 'ห้องน้ำ', 'ที่จอดรถ']
    for col in cat_cols:
        if col in df.columns:
            df[col] = df[col].astype('category')

    # Float32 Downcasting for Numeric Columns
    float_cols = ['ละติจูด', 'ลองจิจูด', 'พื้นที่ใช้สอย (ตร.ม.)', 'พื้นที่_ตารางวา', 'ราคาต่อตารางวา', 'ราคาต่อตารางเมตร']
    for col in float_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').astype('float32')

    # Save to Parquet with ZSTD Compression
    df.to_parquet(output_file, index=False, compression='zstd')
    
    parquet_size = os.path.getsize(output_file) / (1024 * 1024)
    duration = time.time() - start_time
    
    print("\n" + "="*55)
    print(f"[SUCCESS] OPTIMIZED & SAVED TO: {output_file}")
    print(f"Total Rows: {total_rows:,}")
    print(f"Final Compressed Parquet Size: {parquet_size:.2f} MB")
    print(f"Time Elapsed: {duration:.2f} seconds")
    print("="*55)

if __name__ == "__main__":
    optimize_and_convert()
