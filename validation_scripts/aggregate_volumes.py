import os
import pandas as pd

def aggregate_volumes():
    # Assuming this script is in 'validation_scripts/'
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    experiments_dir = os.path.join(root_dir, 'experiments')
    validation_dir = os.path.join(experiments_dir, '_validation_csvs')
    if not os.path.exists(validation_dir):
        os.makedirs(validation_dir)
    output_csv = os.path.join(validation_dir, 'volume_comparison_summary.csv')
    
    rows = []
    # Identify experiment folders
    experiment_folders = [f for f in os.listdir(experiments_dir) 
                          if os.path.isdir(os.path.join(experiments_dir, f)) 
                          and not f.startswith('_')]
    
    for folder in experiment_folders:
        # POINTED TO THE CORRECT EVALUATION SUBFOLDER
        vol_path = os.path.join(experiments_dir, folder, 'evaluation', 'volume_comparison.csv')
        
        if os.path.exists(vol_path):
            df = pd.read_csv(vol_path)
            df['Experiment'] = folder
            rows.append(df)
        else:
            print(f"Warning: Could not find {vol_path}")
    
    if rows:
        combined_df = pd.concat(rows, ignore_index=True)
        combined_df.to_csv(output_csv, index=False)
        print(f"Successfully generated: {output_csv}")
    else:
        print("No volume_comparison.csv files found.")

if __name__ == "__main__":
    aggregate_volumes()