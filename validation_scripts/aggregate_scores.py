import os
import pandas as pd

def aggregate_scores():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    experiments_dir = os.path.join(root_dir, 'experiments')
    validation_dir = os.path.join(experiments_dir, '_validation_csvs')
    if not os.path.exists(validation_dir):
        os.makedirs(validation_dir)
    output_csv = os.path.join(validation_dir, 'score_summary.csv')
    
    rows = []
    experiment_folders = [f for f in os.listdir(experiments_dir) 
                          if os.path.isdir(os.path.join(experiments_dir, f)) 
                          and not f.startswith('_')]
    
    for folder in experiment_folders:
        score_path = os.path.join(experiments_dir, folder, 'output', 'scorestats.csv')
        
        if os.path.exists(score_path):
            df = pd.read_csv(score_path, sep=';')
            # Grab the last row (iteration 10)
            final_score = df.iloc[-1]['avg_executed']
            rows.append({'Experiment': folder, 'Final_Score': final_score})
    
    if rows:
        pd.DataFrame(rows).to_csv(output_csv, index=False, sep=';')
        print(f"Successfully generated: {output_csv}")

if __name__ == "__main__":
    aggregate_scores()