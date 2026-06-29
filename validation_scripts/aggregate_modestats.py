import os
import pandas as pd

def aggregate_modestats():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    experiments_dir = os.path.join(root_dir, 'experiments')
    validation_dir = os.path.join(experiments_dir, '_validation_csvs')
    if not os.path.exists(validation_dir):
        os.makedirs(validation_dir)
    output_csv = os.path.join(validation_dir, 'mode_comparison_summary.csv')

    rows = []
    
    # Get all experiment folders, ignoring hidden ones
    experiment_folders = [f for f in os.listdir(experiments_dir) 
                          if os.path.isdir(os.path.join(experiments_dir, f)) 
                          and not f.startswith('_')]
    
    for folder in experiment_folders:
        stats_path = os.path.join(experiments_dir, folder, 'output', 'modestats.csv')
        
        if os.path.exists(stats_path):
            # Explicitly define columns to handle potential parsing issues
            df = pd.read_csv(stats_path, sep=';')
            
            # Ensure the column names are clean (remove potential leading/trailing spaces)
            df.columns = df.columns.str.strip()
            
            df['Experiment'] = folder
            rows.append(df)
        else:
            print(f"Warning: modestats.csv not found for {folder} at {stats_path}")
    
    if rows:
        # Combine all mode stats into one master CSV
        combined_df = pd.concat(rows, ignore_index=True)
        combined_df.to_csv(output_csv, index=False, sep=';')
        print(f"Successfully generated: {output_csv}")
    else:
        print("No modestats.csv files found.")

if __name__ == "__main__":
    aggregate_modestats()