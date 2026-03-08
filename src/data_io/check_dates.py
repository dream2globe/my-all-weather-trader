import pandas as pd
import glob
import os

for f in glob.glob("data/raw/*.csv"):
    df = pd.read_csv(f)
    print(f"{os.path.basename(f)}: {df['Date'].min()} ~ {df['Date'].max()} (Rows: {len(df)})")
