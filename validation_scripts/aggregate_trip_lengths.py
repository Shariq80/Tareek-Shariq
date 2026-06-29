import os
import pandas as pd

def aggregate_trip_lengths():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    experiments_dir = os.path.join(root_dir, 'experiments')
    validation_dir = os.path.join(experiments_dir, '_validation_csvs')
    if not os.path.exists(validation_dir):
        os.makedirs(validation_dir)
    output_csv = os.path.join(validation_dir, 'trip_length_summary.csv')
    
    rows = []
    # Identify experiment folders
    experiment_folders = [f for f in os.listdir(experiments_dir) 
                          if os.path.isdir(os.path.join(experiments_dir, f)) 
                          and not f.startswith('_')]
    
    for folder in experiment_folders:
        stats_path = os.path.join(experiments_dir, folder, 'output', 'traveldistancestats.csv')
        
        if os.path.exists(stats_path):
            df = pd.read_csv(stats_path, sep=';')
            # Filter for Iteration 10
            final_data = df[df['ITERATION'] == 10].copy()
            final_data['Experiment'] = folder
            rows.append(final_data)
    
    if rows:
        combined_df = pd.concat(rows, ignore_index=True)
        # Reorder columns to put Experiment first
        cols = ['Experiment'] + [c for c in combined_df.columns if c != 'Experiment']
        combined_df = combined_df[cols]
        combined_df.to_csv(output_csv, index=False, sep=';')
        print(f"Successfully generated: {output_csv}")

if __name__ == "__main__":
    aggregate_trip_lengths()