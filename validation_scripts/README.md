# Overview

This repository contains tools to aggregate, validate, and visualize MATSim experiment results. Data processing is managed by a suite of scripts in `validation_scripts`, which store structured outputs in a dedicated directory for the `dashboard.py` application.

## Directory Structure

* `experiments/`: Contains raw simulation output folders.
* `experiments/_validation_csvs/`: Centralized storage for all aggregated CSV files used by the dashboard.
* `validation_scripts/`: Contains Python scripts for data extraction and aggregation.
* `dashboard.py`: Streamlit application for experiment comparison and spatial analysis.

## validation_scripts

The `validation_scripts` folder contains several Python scripts designed to aggregate and analyze data from experiment results. These scripts save their outputs to `experiments/_validation_csvs/`.

* `aggregate_counts.py`: Aggregates count data and calculates GEH statistics.
* `aggregate_metrics.py`: Aggregates performance metrics (JSON summaries).
* `aggregate_modestats.py`: Aggregates mode statistics.
* `aggregate_scores.py`: Aggregates overall plan satisfaction scores.
* `aggregate_trip_lengths.py`: Aggregates trip distance data.
* `aggregate_volumes.py`: Aggregates volume data for device validation.
* `extract_coords.py`: Extracts node coordinates from `network.xml`.
* `run_all.py`: An orchestrator that executes all aggregation scripts in sequence.

### How to Run validation_scripts

1. Navigate to the project root folder:
   ```bash
   cd "Tareek"
   ```
2. Run the pipeline:
   ```bash
   python validation_scripts/run_all.py
   ```

This will automatically generate or update all necessary files in `experiments/_validation_csvs/`.

## dashboard.py

The `dashboard.py` file is a Streamlit application providing a unified interface for experiment comparison.

### How to Run dashboard.py

1. Navigate to the root directory:
   ```bash
   cd "Tareek"
   ```
2. Install dependencies:
   ```bash
   pip install streamlit
   ```
3. Launch the dashboard:
   ```bash
   streamlit run dashboard.py
   ```

## Key Features

* **Centralized Data:** Automatically reads from `experiments/_validation_csvs/`.
* **Performance Scorecard:** Displays KPIs and rankings across experiments.
* **Interactive Validation:** Tabs for GEH analysis, mode shares, and device-level volume validation.
* **Spatial Analysis:** Map-based visualization of experiment data.

## Example Usage

1. Open `http://localhost:8501` in your browser.
2. Use the tabs to switch between KPIs, Counts Validation, and GEH Analysis.
