import pandas as pd
import os
from pathlib import Path

def station_base(cs_id: str) -> str:
    """Helper to strip direction suffix to match aggregation."""
    sid = str(cs_id).split("+")[0]
    parts = sid.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0]
    return sid

def aggregate_counts():
    # 1. Setup paths
    root_dir = Path(__file__).resolve().parent.parent
    experiments_dir = root_dir / "experiments"
    
    # NEW: Define the dedicated validation folder
    validation_dir = experiments_dir / "_validation_csvs"
    validation_dir.mkdir(exist_ok=True)  # Creates folder if missing
    
    output_csv = validation_dir / "counts_summary_enhanced.csv"
    
    all_data = []
    
    # 2. Automatic Discovery
    folders = [f for f in os.listdir(experiments_dir) 
               if os.path.isdir(experiments_dir / f) and not f.startswith('_')]
    
    for folder_name in folders:
        folder = experiments_dir / folder_name
        iters = folder / "output" / "ITERS"
        
        if not iters.exists():
            print(f"Skipping {folder_name}: No ITERS directory found.")
            continue
            
        candidates = list(iters.glob("it.*/*.countscompare.txt"))
        if not candidates: 
            print(f"Skipping {folder_name}: No .countscompare.txt found.")
            continue
            
        counts_file = sorted(candidates, key=lambda p: int(p.parent.name.split(".")[-1]))[-1]
        
        # 3. Process Data
        df = pd.read_csv(counts_file, sep="\t")
        df.columns = [c.strip() for c in df.columns]
        df = df[['Count Station Id', 'Hour', 'MATSIM volumes', 'Count volumes']]
        df.columns = ['raw_id', 'hour', 'sim', 'obs']
        df['experiment'] = folder_name 
        
        # 4. Per-Direction & Summed Data
        df_dir = df.copy()
        df_dir['station_id'] = df_dir['raw_id']
        df_dir['is_summed'] = False
        all_data.append(df_dir)
        
        df_sum = df.copy()
        df_sum['station_id'] = df_sum['raw_id'].apply(station_base)
        df_sum = df_sum.groupby(['station_id', 'hour', 'experiment'], as_index=False).agg({'sim': 'sum', 'obs': 'sum'})
        df_sum['is_summed'] = True
        all_data.append(df_sum)
            
    # 5. Save final file in the _validation_csvs folder
    if all_data:
        combined_df = pd.concat(all_data)
        combined_df['sim'] = combined_df['sim'].clip(lower=1)
        combined_df['obs'] = combined_df['obs'].clip(lower=1)
        
        combined_df['geh'] = ((2 * (combined_df['sim'] - combined_df['obs'])**2) / 
                             (combined_df['sim'] + combined_df['obs'])).pow(0.5)
        
        combined_df.to_csv(output_csv, index=False)
        print(f"Successfully generated: {output_csv}")
    else:
        print("No experiment data processed.")

if __name__ == "__main__":
    aggregate_counts()