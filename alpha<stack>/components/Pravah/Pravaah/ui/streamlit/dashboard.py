import streamlit as st
import requests
import pandas as pd
import json
import os
from datetime import datetime

# --- Configuration ---
API_BASE_URL = os.getenv("PRAVAH_API_URL", "http://localhost:8000/api/v1")

# --- Page Configuration ---
st.set_page_config(
    page_title="Pravah: High-Performance File & Data Processing Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Helper Functions ---
@st.cache_data(ttl=60) # Cache data for 60 seconds
def get_all_jobs(api_url):
    try:
        response = requests.get(f"{api_url}/jobs")
        response.raise_for_status()
        jobs = response.json()
        return jobs
    except requests.exceptions.ConnectionError:
        st.error(f"Could not connect to the Pravah API at `{api_url}`. Please ensure the backend is running.")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching jobs: {e}")
        return None

@st.cache_data(ttl=30)
def get_job_details(api_url, job_id):
    try:
        response = requests.get(f"{api_url}/jobs/{job_id}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching job details for {job_id}: {e}")
        return None

@st.cache_data(ttl=30)
def get_job_results(api_url, job_id):
    try:
        response = requests.get(f"{api_url}/jobs/{job_id}/results")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        if response.status_code == 404:
            st.warning(f"No results found for job ID: `{job_id}` or job not yet completed.")
            return None
        st.error(f"Error fetching job results for {job_id}: {e}")
        return None

def format_timestamp(ts):
    if ts:
        try:
            # Handle ISO 8601 with or without Z and potentially without microseconds
            if '.' in ts and 'Z' in ts: # e.g., "2023-10-27T10:00:00.123456Z"
                return datetime.fromisoformat(ts.replace('Z', '+00:00')).strftime("%Y-%m-%d %H:%M:%S")
            elif 'Z' in ts: # e.g., "2023-10-27T10:00:00Z"
                return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S")
            else: # e.g., "2023-10-27T10:00:00"
                return datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return ts # Return original if invalid format
    return "N/A"

# --- Main Dashboard Layout ---
st.title("🌊 Pravah: File & Data Processing Dashboard")
st.markdown("Monitor the status and progress of your high-performance Pravah jobs.")

# --- Sidebar Configuration and API Connection Test ---
st.sidebar.header("Configuration")
api_url_input = st.sidebar.text_input("Pravah API URL", API_BASE_URL, key="api_url_input")

if st.sidebar.button("Test API Connection 🔌"):
    try:
        # Assuming a simple /health endpoint exists as per project description
        response = requests.get(f"{api_url_input}/health")
        if response.status_code == 200:
            st.sidebar.success(f"Successfully connected to API at `{api_url_input}`")
        else:
            st.sidebar.error(f"API connection failed with status code {response.status_code}.")
            st.sidebar.code(response.text)
    except requests.exceptions.ConnectionError:
        st.sidebar.error(f"Could not connect to API at `{api_url_input}`. Is the backend running?")
    except Exception as e:
        st.sidebar.error(f"An unexpected error occurred during connection test: {e}")

# --- Job Listing ---
st.header("All Processing Jobs")

col_buttons, col_spacer = st.columns([0.2, 0.8])
with col_buttons:
    if st.button("Refresh Jobs List 🔄", use_container_width=True):
        st.cache_data.clear() # Clear all caches to force data reload
        st.rerun() # Rerun the app to fetch new data

jobs = get_all_jobs(api_url_input)

if jobs is not None:
    if jobs:
        df_jobs = pd.DataFrame(jobs)
        
        # Ensure 'job_id' is the first column for selection clarity
        if 'job_id' in df_jobs.columns:
            df_jobs = df_jobs[['job_id'] + [col for col in df_jobs.columns if col != 'job_id']]

        # Convert 'created_at' to datetime and sort
        if 'created_at' in df_jobs.columns:
            df_jobs['created_at'] = pd.to_datetime(df_jobs['created_at'], errors='coerce')
            df_jobs = df_jobs.sort_values(by='created_at', ascending=False)
            df_jobs['created_at'] = df_jobs['created_at'].dt.strftime("%Y-%m-%d %H:%M:%S") # Format back for display

        # Apply timestamp formatting to other relevant columns
        for col in ['started_at', 'completed_at', 'failed_at']:
            if col in df_jobs.columns:
                df_jobs[col] = df_jobs[col].apply(format_timestamp)

        # Calculate duration_seconds if not provided by API
        if 'started_at' in df_jobs.columns and 'completed_at' in df_jobs.columns and 'duration_seconds' not in df_jobs.columns:
            # Note: This is client-side calculation and might not be perfectly accurate if API provides it
            df_jobs['temp_started'] = pd.to_datetime(df_jobs['started_at'], errors='coerce', format="%Y-%m-%d %H:%M:%S")
            df_jobs['temp_completed'] = pd.to_datetime(df_jobs['completed_at'], errors='coerce', format="%Y-%m-%d %H:%M:%S")
            df_jobs['duration_seconds'] = (df_jobs['temp_completed'] - df_jobs['temp_started']).dt.total_seconds().fillna(0).astype(int)
            df_jobs = df_jobs.drop(columns=['temp_started', 'temp_completed'])
            
        # Select relevant columns for display in the table
        display_cols = [
            'job_id', 'status', 'job_type', 'input_path', 'output_path',
            'created_at', 'started_at', 'completed_at', 'duration_seconds',
            'total_files_processed', 'files_failed_to_process', 'errors' # Assuming these fields from job model
        ]
        
        # Filter for columns that actually exist in the DataFrame
        existing_display_cols = [col for col in display_cols if col in df_jobs.columns]
        display_df = df_jobs[existing_display_cols]

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            selection_mode='single-row',
            on_select='rerun', # Rerun the app when a row is selected
            key='job_table'
        )

        # Check if a row was selected and update session state
        selected_rows = st.session_state.get('job_table', {}).get('selection', {}).get('rows', [])
        if selected_rows:
            selected_job_id = df_jobs.iloc[selected_rows[0]]['job_id']
            st.session_state['selected_job_id'] = selected_job_id
        elif 'selected_job_id' not in st.session_state:
            st.session_state['selected_job_id'] = None

    else:
        st.info("No processing jobs found yet. Submit a job via the API or CLI to see it here!")
else:
    st.warning("Cannot retrieve jobs. Check API connection or backend logs for more details.")


# --- Job Details Section ---
if st.session_state.get('selected_job_id'):
    st.markdown("---")
    st.header(f"Details for Job ID: `{st.session_state['selected_job_id']}`")

    job_details = get_job_details(api_url_input, st.session_state['selected_job_id'])
    if job_details:
        col1_detail, col2_detail = st.columns(2)
        with col1_detail:
            st.subheader("Job Information")
            st.json(job_details) # Display raw JSON for full details

        with col2_detail:
            st.subheader("Job Results")
            job_results = get_job_results(api_url_input, st.session_state['selected_job_id'])
            if job_results:
                if isinstance(job_results, dict):
                    st.json(job_results)
                elif isinstance(job_results, list):
                    st.dataframe(pd.DataFrame(job_results), use_container_width=True, hide_index=True)
                else:
                    st.write(job_results)
            else:
                st.info("No detailed results available yet, or job is still in progress/failed.")
    else:
        st.warning(f"Could not load details for job ID: `{st.session_state['selected_job_id']}`. It might have been deleted or never existed.")

else:
    st.info("Select a job from the table above to view its details, or refresh the list if jobs are missing.")

st.markdown("---")
st.caption(f"Pravah Dashboard running against API: `{api_url_input}`")