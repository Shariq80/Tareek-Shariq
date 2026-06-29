import json
import os
import csv

def generate_comparison_csv():
    # 1. Setup paths
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    experiments_dir = os.path.join(root_dir, 'experiments')
    
    # NEW: Define the dedicated validation folder
    validation_dir = os.path.join(experiments_dir, '_validation_csvs')
    if not os.path.exists(validation_dir):
        os.makedirs(validation_dir)
        
    output_csv = os.path.join(validation_dir, 'comparison_summary.csv')
    
    # Metrics we want to track in our dashboard
    metrics_to_track = [
        'experiment_name', 'mean_geh', 'rmse', 'mae', 
        'correlation', 'peak_hour_correlation', 'median_station_ratio',
        'interquartile_mean_ratio'
    ]
    
    rows = []
    
    # 2. Automatic Discovery
    experiment_folders = [f for f in os.listdir(experiments_dir) 
                          if os.path.isdir(os.path.join(experiments_dir, f)) 
                          and not f.startswith('_')]
    
    for folder in experiment_folders:
        metrics_path = os.path.join(experiments_dir, folder, 'evaluation', 'summary_metrics.json')
        
        if os.path.exists(metrics_path):
            with open(metrics_path, 'r') as f:
                data = json.load(f)
                # OVERRIDE: Use the folder name as the official experiment name
                data['experiment_name'] = folder 
                
                row = {key: data.get(key) for key in metrics_to_track}
                rows.append(row)
    
    # 3. Write to CSV inside the validation directory
    with open(output_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=metrics_to_track)
        writer.writeheader()
        writer.writerows(rows)
        
    print(f"Successfully generated: {output_csv}")

if __name__ == "__main__":
    generate_comparison_csv()