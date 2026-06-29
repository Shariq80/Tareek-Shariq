import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import numpy as np

st.set_page_config(page_title="Experiment Dashboard", layout="wide")
st.title("One-Stop Experiment Comparison")

experiments_dir = 'experiments'
validation_dir = os.path.join(experiments_dir, '_validation_csvs')

# --- GLOBAL DATA LOADING & INITIALIZATION ---
counts_path = os.path.join(validation_dir, 'counts_summary_enhanced.csv')
coords_path = 'station_coords.csv'

# Initialize session state for synchronization
if 'selected_hour' not in st.session_state:
    st.session_state['selected_hour'] = 7
if 'selected_station' not in st.session_state:
    st.session_state['selected_station'] = None

df = None
if os.path.exists(counts_path) and os.path.exists(coords_path):
    df_counts = pd.read_csv(counts_path)
    df_coords = pd.read_csv(coords_path)

    df_counts['station_id'] = df_counts['station_id'].astype(str).str.strip()
    df_coords['station_id'] = df_coords['station_id'].astype(str).str.strip()

    df = pd.merge(df_counts, df_coords, on='station_id', how='left')

    # Calculate GEH globally
    df['geh'] = np.sqrt((2 * (df['sim'] - df['obs'])**2) / ((df['sim'] + df['obs']) + 1e-9))

else:
    st.error("Data files not found. Ensure 'counts_summary_enhanced.csv' and 'station_coords.csv' exist.")

# --- PERFORMANCE SCORECARD ---
if df is not None:
    st.subheader("Experiment Performance Leaderboard")
    leaderboard = df.groupby('experiment').agg({
        'geh': 'mean',
        'station_id': 'count'
    }).rename(columns={'geh': 'Mean GEH', 'station_id': 'Station Count'})
    
    pass_rates = df.groupby('experiment').apply(lambda x: (x['geh'] < 5).mean() * 100)
    leaderboard['Pass Rate (%)'] = pass_rates
    st.dataframe(leaderboard.sort_values('Mean GEH'), use_container_width=True)

# Create Tabs
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["Performance KPIs", "Mode Share", "Spatial Analysis", "Model Satisfaction", "Device Validation", "Counts Validation", "GEH Analysis"])

# --- TAB 1: PERFORMANCE KPIS ---
with tab1:
    if os.path.exists(os.path.join(validation_dir, 'comparison_summary.csv')):
        df_metrics = pd.read_csv(os.path.join(validation_dir, 'comparison_summary.csv'))
        st.subheader("Performance KPIs")
        st.dataframe(df_metrics)
        
        fig_kpi = px.bar(
            df_metrics, 
            x='experiment_name', 
            y='mean_geh',
            labels={'experiment_name': 'Experiment', 'mean_geh': 'Mean GEH'},
            text_auto='.2f'
        )
        fig_kpi.update_xaxes(tickangle=0)
        st.plotly_chart(fig_kpi)

# --- TAB 2: MODE SHARE ---
with tab2:
    mode_path = os.path.join(validation_dir, 'mode_comparison_summary.csv')
    if os.path.exists(mode_path):
        df_mode = pd.read_csv(mode_path, sep=';')
        st.subheader("Mode Share (Final Iteration 10)")
        
        final_df = df_mode[df_mode['iteration'] == 10]
        df_long = final_df.melt(id_vars=['Experiment'], value_vars=['car', 'pt', 'walk'], 
                                var_name='Mode', value_name='Share')
        
        fig_mode = px.bar(df_long, x='Experiment', y='Share', color='Mode', 
                         text_auto='.2f', labels={'Share': 'Mode Share (Proportion)'})
        fig_mode.update_xaxes(tickangle=0)
        st.plotly_chart(fig_mode)

# --- TAB 3: ANALYSIS ---
with tab3:
    # 1. TRIP DISTANCE ANALYSIS
    st.subheader("Final Trip Distance Comparison (Iteration 10)")
    trip_path = os.path.join(validation_dir, 'trip_length_summary.csv')
    if os.path.exists(trip_path):
        df_trips = pd.read_csv(trip_path, sep=';')
        fig_trips = px.bar(df_trips, x='Experiment', y='avg. Average Trip distance',
                           labels={'avg. Average Trip distance': 'Avg Trip Distance (m)'}, text_auto='.0f')
        fig_trips.update_xaxes(tickangle=0)
        st.plotly_chart(fig_trips, use_container_width=True)
    else:
        st.info("Trip data not found.")

# Add this tab structure to your dashboard.py
with tab4:
    st.subheader("Final Simulation Satisfaction Score")
    score_path = os.path.join(validation_dir, 'score_summary.csv')
    if os.path.exists(score_path):
        df_scores = pd.read_csv(score_path, sep=';')
        
        fig_score = px.bar(
            df_scores, 
            x='Experiment', 
            y='Final_Score',
            title="Higher is better (Plan satisfaction)",
            labels={'Final_Score': 'Average Executed Score'},
            text_auto='.0f'
        )
        fig_score.update_xaxes(tickangle=0)
        st.plotly_chart(fig_score)

# --- TAB: DEVICE VALIDATION ---
with tab5:
    st.subheader("Device/Station Validation")
    vol_summary_path = os.path.join(validation_dir, 'volume_comparison_summary.csv')
    
    if os.path.exists(vol_summary_path):
        df_vol = pd.read_csv(vol_summary_path)
        
        # 1. Performance Summary
        st.subheader("Performance Summary")
        geh_summary = df_vol.groupby('device_id')['geh'].mean().reset_index()
        col1, col2 = st.columns(2)
        with col1:
            st.write("Top 3 Best Performing (Lowest GEH)")
            st.table(geh_summary.nsmallest(3, 'geh').set_index('device_id'))
        with col2:
            st.write("Top 3 Worst Performing (Highest GEH)")
            st.table(geh_summary.nlargest(3, 'geh').set_index('device_id'))
            
        st.divider()

        # 2. Controls
        all_devices = sorted(df_vol['device_id'].unique().tolist())
        if 'device_idx' not in st.session_state:
            st.session_state['device_idx'] = 0
            
        selected_device = st.selectbox("Select Device (Type to search):", all_devices, index=st.session_state['device_idx'])
        st.session_state['device_idx'] = all_devices.index(selected_device)
        compare_mode = st.checkbox("Compare across all experiments")
        
        # 3. Data Processing & Plotting
        device_data = df_vol[df_vol['device_id'] == selected_device]
        
        if compare_mode:
            fig = px.line(device_data, x='hour', y='simulated', color='Experiment', title=f"Comparison: {selected_device}", markers=True)
            obs_data = device_data.drop_duplicates(subset=['hour'])
            fig.add_scatter(x=obs_data['hour'], y=obs_data['observed'], name='Observed (Ground Truth)', line=dict(color='white', dash='dash', width=3))
            st.plotly_chart(fig, use_container_width=True)
            
            # --- FIXED ALIGNMENT ROW ---
            c1, c2 = st.columns([0.85, 0.15])
            with c1:
                st.subheader(f"Validation Metrics: {selected_device}")
            with c2:
                # Aligning buttons by creating a sub-row for them
                b1, b2 = st.columns(2)
                if b1.button("⬅", key="prev_c"):
                    st.session_state['device_idx'] = (st.session_state['device_idx'] - 1) % len(all_devices); st.rerun()
                if b2.button("➡", key="next_c"):
                    st.session_state['device_idx'] = (st.session_state['device_idx'] + 1) % len(all_devices); st.rerun()
            
            metrics = device_data.groupby('Experiment').apply(lambda x: pd.Series({"MAE": f"{x['abs_error'].mean():.1f}", "RMSE": f"{(x['error']**2).mean()**0.5:.1f}", "Mean GEH": f"{x['geh'].mean():.2f}", "Correlation": f"{x[['observed', 'simulated']].corr().iloc[0, 1]:.3f}"})).reset_index()
            st.table(metrics)
            
        else:
            exp_list = sorted(device_data['Experiment'].unique().tolist())
            selected_exp = st.selectbox("Select Experiment", exp_list)
            exp_df = device_data[device_data['Experiment'] == selected_exp]
            
            fig = px.line(exp_df, x='hour', y=['observed', 'simulated'], title=f"Traffic Flow: {selected_device} ({selected_exp})", markers=True)
            st.plotly_chart(fig, use_container_width=True)
            
            # --- FIXED ALIGNMENT ROW ---
            c1, c2 = st.columns([0.85, 0.15])
            with c1:
                st.subheader(f"Metrics: {selected_exp}")
            with c2:
                b1, b2 = st.columns(2)
                if b1.button("⬅", key="prev_s"):
                    st.session_state['device_idx'] = (st.session_state['device_idx'] - 1) % len(all_devices); st.rerun()
                if b2.button("➡", key="next_s"):
                    st.session_state['device_idx'] = (st.session_state['device_idx'] + 1) % len(all_devices); st.rerun()

            metric_data = {"Metric": ["MAE", "RMSE", "Mean GEH", "Correlation"], "Value": [f"{exp_df['abs_error'].mean():.1f}", f"{(exp_df['error']**2).mean()**0.5:.1f}", f"{exp_df['geh'].mean():.2f}", f"{exp_df[['observed', 'simulated']].corr().iloc[0, 1]:.3f}"]}
            st.table(pd.DataFrame(metric_data))
    else:
        st.error("Summary file not found.")# with tab5:

with tab6: # Counts Validation
    st.subheader("Counts Validation (Log-Log)")
    if df is not None:
        col1, col2 = st.columns([1, 2])
        with col1:
            sum_mode = st.checkbox("Sum Directions", value=True, key='sum_mode_check')
            connect_mode = st.checkbox("Connect Stations", value=False)
        
        with col2:
            peak_choice = st.radio("Select Hour Mode:", ["Standard", "Custom"], horizontal=True)
        
        plot_df = df[df['is_summed'] == sum_mode]
        
        if peak_choice == "Standard":
            selected_hour = st.selectbox("Select Peak Hour", [7, 8, 16, 17], key='std_hour')
        else:
            selected_hour = st.selectbox("Select Custom Hour", sorted(plot_df['hour'].unique()), key='cust_hour')
        
        # Sync with global state
        st.session_state['selected_hour'] = selected_hour
            
        hour_df = plot_df[plot_df['hour'] == selected_hour].copy()
        
        # Calculate visual bounds for the identity line
        min_val = max(1, min(hour_df['obs'].min(), hour_df['sim'].min()))
        max_val = max(hour_df['obs'].max(), hour_df['sim'].max())
        
        highlight_sid = st.session_state.get('selected_station')
        fig = go.Figure()
        
        # Plot markers
        for exp in hour_df['experiment'].unique():
            exp_data = hour_df[hour_df['experiment'] == exp]
            # Dim non-selected points
            opacity = 0.2 if highlight_sid and (exp_data['station_id'] != highlight_sid).any() else 1.0
            
            fig.add_trace(go.Scatter(
                x=exp_data['obs'], y=exp_data['sim'],
                mode='markers', name=exp,
                marker=dict(size=6, opacity=opacity),
                text=exp_data['station_id'],
                hovertemplate="Station: %{text}<br>Obs: %{x}<br>Sim: %{y}<br>GEH: %{customdata:.2f}<extra>%{fullData.name}</extra>",
                customdata=exp_data['geh'] 
            ))
            
        # Add connecting lines if requested
        if connect_mode:
            for sid in hour_df['station_id'].unique():
                sid_data = hour_df[hour_df['station_id'] == sid].sort_values('experiment')
                if len(sid_data) >= 2:
                    fig.add_trace(go.Scatter(
                        x=sid_data['obs'], y=sid_data['sim'], 
                        mode='lines', line=dict(color="gray", width=0.5), 
                        showlegend=False, hoverinfo='skip', opacity=0.3
                    ))

        fig.update_layout(
            title=f"Log-Log Comparison: Hour {selected_hour:02d}:00", 
            xaxis=dict(type="log", title="Observed Volumes"), 
            yaxis=dict(type="log", title="Simulated Volumes"), 
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        fig.add_shape(type="line", x0=min_val, y0=min_val, x1=max_val, y1=max_val, line=dict(color="white", dash="dash"))
        st.plotly_chart(fig)
    else:
        st.error("Counts summary data not available.")

with tab7: # GEH Analysis
    st.subheader("GEH Statistical Analysis")
    if df is not None:
        # Use the sum_mode state from tab6 for consistency
        sum_mode = st.session_state.get('sum_mode_check', True)
        plot_df = df[df['is_summed'] == sum_mode]
        hour_df = plot_df[plot_df['hour'] == st.session_state['selected_hour']].copy()
        
        # 1. Metrics & Threshold Slider
        col_stats1, col_stats2, col_slider = st.columns([1, 1, 2])
        with col_stats1: 
            st.metric("Mean GEH", f"{hour_df['geh'].mean():.2f}")
        with col_slider: 
            threshold = st.slider("Passing Threshold (GEH < X)", 1.0, 15.0, 5.0, key='geh_threshold')
        with col_stats2: 
            st.metric(f"Stations Passing (GEH < {threshold})", f"{(hour_df['geh'] < threshold).mean() * 100:.1f}%")
            
        # 2. Histogram
        fig_hist = px.histogram(
            hour_df, x="geh", color="experiment", nbins=40, 
            title="GEH Value Distribution", labels={'geh': 'GEH Statistic'}, marginal="box"
        )
        fig_hist.add_vline(x=threshold, line_dash="dash", line_color="red")
        st.plotly_chart(fig_hist, use_container_width=True)
        
        # 3. Interactive Station Data
        st.write("### Station-level GEH Data")
        display_df = hour_df[['station_id', 'experiment', 'sim', 'obs', 'geh']].sort_values('geh', ascending=False)
        
        # Use event-based selection for interactivity
        event = st.dataframe(
            display_df, use_container_width=True, 
            selection_mode="single-row", on_select="rerun"
        )
        
        # 4. Handle Selection
        if event.selection.rows:
            st.session_state['selected_station'] = display_df.iloc[event.selection.rows[0]]['station_id']
            st.success(f"Highlighting station: {st.session_state['selected_station']}")
        else:
            st.session_state['selected_station'] = None

        # 5. Download Button
        csv = display_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download GEH Results as CSV", 
            data=csv, 
            file_name=f"geh_{st.session_state['selected_hour']:02d}.csv", 
            mime='text/csv'
        )
    else:
        st.error("Data not available. Check your files.")
