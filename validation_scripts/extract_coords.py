import xml.etree.ElementTree as ET
import pandas as pd
import os

def extract_all_network_coords(experiments_dir):
    all_data = []
    
    # Iterate through each folder in the experiments directory
    for experiment_name in os.listdir(experiments_dir):
        exp_path = os.path.join(experiments_dir, experiment_name)
        network_path = os.path.join(exp_path, 'network.xml')
        
        if os.path.isdir(exp_path) and os.path.exists(network_path):
            print(f"--- Processing: {experiment_name} ---")
            try:
                tree = ET.parse(network_path)
                root = tree.getroot()
                
                nodes_found = 0
                for node in root.findall('.//node'):
                    # FIX: Use 'id' attribute since 'name' does not exist in your XML
                    station_id = node.get('id') 
                    
                    if station_id:
                        all_data.append({
                            'station_id': station_id,
                            'x': float(node.get('x', 0)),
                            'y': float(node.get('y', 0))
                        })
                        nodes_found += 1
                
                print(f"Extracted {nodes_found} nodes from {experiment_name}")
            except Exception as e:
                print(f"Could not parse {network_path}: {e}")
    
    if not all_data:
        print("CRITICAL: No nodes were found. Check your network.xml file structure.")
        return

    # Create DataFrame
    df = pd.DataFrame(all_data).drop_duplicates(subset=['station_id'])
    
    # Save to root folder
    output_path = os.path.join(os.path.dirname(experiments_dir), 'station_coords.csv')
    df.to_csv(output_path, index=False)
    print(f"Successfully saved {len(df)} unique stations to: {output_path}")
    print("Sample of extracted data:")
    print(df.head())

# Run script
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
experiments_dir = os.path.join(root_dir, 'experiments')

extract_all_network_coords(experiments_dir)