import streamlit as st
import requests
import numpy as np

# Set up Streamlit page
st.set_page_config(page_title="Ball Screw Drive Monitoring", layout="wide")

# API URLs (modify if needed)
FLASK_API_URL = "http://localhost:5000"
PREDICTION_API_URL = "http://localhost:5001"

st.title("Ball Screw Drive Monitoring")

# Health check for databases
st.header("System Health Check")
if st.button("Check System Health"):
    try:
        response = requests.get(f"{FLASK_API_URL}/db-check")
        if response.status_code == 200:
            health_data = response.json()
            st.success(f"InfluxDB Status: {health_data['influxdb_status']}")
            st.success(f"PostgreSQL Version: {health_data['postgres_version']}")
        else:
            st.error("Failed to retrieve health data.")
    except Exception as e:
        st.error(f"Error connecting to health check API: {e}")

# Anomaly detection input and prediction
st.header("Anomaly Detection")
st.write("Enter vibration data points for prediction.")

# Placeholder data input for prediction
data_input = st.text_area("Input Data (comma-separated values)", "0.5, 0.2, -0.3, 0.1")
if st.button("Run Prediction"):
    try:
        # Convert input to list
        data = list(map(float, data_input.split(",")))
        response = requests.post(f"{PREDICTION_API_URL}/predict", json={"data": data})
        
        if response.status_code == 200:
            result = response.json()
            st.success(f"Anomaly Score: {result['anomaly_score']:.2f}")
        else:
            st.error("Prediction API returned an error.")
    except Exception as e:
        st.error(f"Error making prediction: {e}")
