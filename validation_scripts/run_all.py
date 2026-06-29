import subprocess
import sys
import os

def run_pipeline():
    # 1. List of your atomic scripts in order
    scripts = [
        ['python', 'validation_scripts/aggregate_metrics.py'],
        ['python', 'validation_scripts/aggregate_modestats.py'],
        ['python', 'validation_scripts/aggregate_trip_lengths.py'],
        ['python', 'validation_scripts/aggregate_scores.py'],
        ['python', 'validation_scripts/aggregate_volumes.py'],
        ['python', 'validation_scripts/aggregate_counts.py'],
    ]
    
    print("--- Starting Data Pipeline ---")
    
    # 2. Execute each atomic script
    for cmd in scripts:
        try:
            print(f"Running {' '.join(cmd)}...")
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error running {cmd}: {e}")
            sys.exit(1) # Stop if a script fails
    
    print("--- Pipeline Complete. Launching Dashboard ---")
    
    # 3. Launch the dashboard
    subprocess.run(['streamlit', 'run', 'dashboard.py'])

if __name__ == "__main__":
    run_pipeline()