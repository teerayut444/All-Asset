import pandas as pd
import numpy as np
import time

t0 = time.time()
df = pd.read_parquet('all_assets.parquet')
print(f"Loaded parquet in {time.time() - t0:.2f}s, shape: {df.shape}")

# Test districts / subdistricts formatting
t1 = time.time()
dist_df = df[['อำเภอ', 'จังหวัด']].drop_duplicates().dropna()
unique_districts_formatted = [f"{row['อำเภอ']} ({row['จังหวัด']})" for _, row in dist_df.iterrows()]
print(f"Districts formatting ({len(unique_districts_formatted)}): {time.time() - t1:.2f}s")

# Test subdistricts formatting
t2 = time.time()
sub_df = df[['ตำบล', 'อำเภอ', 'จังหวัด']].drop_duplicates().dropna()
unique_subdistricts_formatted = [f"{row['ตำบล']} ({row['อำเภอ']}, {row['จังหวัด']})" for _, row in sub_df.iterrows()]
print(f"Subdistricts formatting ({len(unique_subdistricts_formatted)}): {time.time() - t2:.2f}s")

# Check min/max price
valid_prices = df['ราคา'].dropna()
print("Min price:", valid_prices.min(), "Max price:", valid_prices.max())

# Check slider options generation
min_val = int(valid_prices.min())
max_val = int(valid_prices.max())
print("Min val int:", min_val, "Max val int:", max_val)

t3 = time.time()
options = [min_val]
if max_val - min_val > 10000000:
    for v in range(max(100000, (min_val // 100000) * 100000), min(10000000, max_val), 100000):
        if v > min_val:
            options.append(v)
    for v in range(10000000, min(50000000, max_val), 1000000):
        if v > options[-1]:
            options.append(v)
    for v in range(50000000, min(200000000, max_val), 5000000):
        if v > options[-1]:
            options.append(v)
    for v in range(200000000, max_val, 20000000):
        if v > options[-1]:
            options.append(v)
if max_val > options[-1]:
    options.append(max_val)
options = sorted(list(set(options)))
print(f"Options generated in {time.time() - t3:.4f}s, length: {len(options)}")
