import pandas as pd
import numpy as np
from pathlib import Path
import traceback

def test():
    try:
        import app
        print("Imported app successfully!")
        df = app.load_properties_data()
        print("Data loaded shape:", df.shape if df is not None else None)
        print("Columns in loaded data:", list(df.columns) if df is not None else None)
    except Exception as e:
        print("ERROR during data loading:")
        traceback.print_exc()

test()
