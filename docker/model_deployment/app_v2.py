from flask import Flask, request, jsonify, render_template
import numpy as np
import tensorflow as tf
import logging
import joblib
import psycopg2
import smtplib
from email.mime.text import MIMEText
from apscheduler.schedulers.background import BackgroundScheduler

# Initialize Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Load resources
MODEL_PATH = "/home/rafzarf/Code/ta_rafza_containerized/docker/model_deployment/pretrained_model/lstm_autoencoder_model.keras"
SCALER_PATH = "/home/rafzarf/Code/ta_rafza_containerized/docker/model_deployment/pretrained_model/scaler.save"
PCA_MODEL_PATH = "/home/rafzarf/Code/ta_rafza_containerized/docker/model_deployment/pretrained_model/pca_model.pkl"
GBR_MODEL_PATH = "/home/rafzarf/Code/ta_rafza_containerized/docker/model_deployment/pretrained_model/rul_gbr_model_pca.pkl"

model = tf.keras.models.load_model(MODEL_PATH)
scaler = joblib.load(SCALER_PATH)
pca_model = joblib.load(PCA_MODEL_PATH)
gbr_model = joblib.load(GBR_MODEL_PATH)

# Email configuration
EMAIL_ADDRESS = "xxrafzaxx@gmail.com"
EMAIL_PASSWORD = "NaonAiKamu28"
ALERT_RECIPIENTS = ["xxrafzaxx@gmail.com"]

# Database configuration
DB_CONFIG = {
    "dbname": "ta_rafza_db",
    "user": "rafzarf",
    "password": "Rf28012002@postgres",
    "host": "localhost",
}

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

# Thresholds for classification
ISO_CLASS_I_THRESHOLDS = {
    "A (Good)": 0.71,
    "B (Acceptable)": 1.12,
    "C (Alert)": 1.8,
    "D (Not Allowed)": np.inf,
}


def preprocess_data(batch_data):
    """Preprocess and scale incoming batch data."""
    processed_data = []
    for data in batch_data:
        x, y, z, acc = data["x"], data["y"], data["z"], data["acceleration"]
        magnitude = np.sqrt(x**2 + y**2 + z**2)

        processed_row = [
            acc, x, y, z, magnitude, acc, 0, x, 0, y, 0, z, 0, magnitude, 0,
            0,  # velocity placeholder
            0,  # acceleration change placeholder
            x / (magnitude + 1e-8), y / (magnitude + 1e-8), z / (magnitude + 1e-8),
            0, 0, 0, magnitude, magnitude  # cumulative, min, max placeholders
        ]
        processed_data.append(processed_row)

    processed_data = np.array(processed_data)
    scaled_data = scaler.transform(processed_data)
    return scaled_data


def estimate_rul_percentage(mse):
    """Estimate Remaining Useful Life (RUL) percentage based on MSE."""
    if mse <= ISO_CLASS_I_THRESHOLDS["A (Good)"]:
        return 100
    elif mse <= ISO_CLASS_I_THRESHOLDS["B (Acceptable)"]:
        return 80
    elif mse <= ISO_CLASS_I_THRESHOLDS["C (Alert)"]:
        return 50
    else:
        return 20


def send_email_alert(mse, classification):
    """Send an email alert for high anomalies."""
    if classification in ["C (Alert)", "D (Not Allowed)"]:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            subject = "Anomaly Detected in Predictive Maintenance System"
            body = f"Anomaly detected with MSE: {mse:.2f}, classified as {classification}."
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = EMAIL_ADDRESS
            msg["To"] = ", ".join(ALERT_RECIPIENTS)
            smtp.send_message(msg)
            logging.info(f"Alert email sent to {', '.join(ALERT_RECIPIENTS)}")


def daily_summary():
    """Send a daily summary email of detected anomalies."""
    cur.execute("SELECT COUNT(*) FROM predictions WHERE classification IN ('C (Alert)', 'D (Not Allowed)')")
    count = cur.fetchone()[0]
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        subject = "Daily Predictive Maintenance System Summary"
        body = f"Total anomalies detected today: {count}"
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = ", ".join(ALERT_RECIPIENTS)
        smtp.send_message(msg)
        logging.info(f"Daily summary email sent to {', '.join(ALERT_RECIPIENTS)}")


scheduler = BackgroundScheduler()
scheduler.add_job(daily_summary, 'interval', hours=24)
scheduler.start()

# API endpoints
@app.route("/predict_rul", methods=["POST"])
def predict_rul():
    data_batch = request.json
    if not data_batch or len(data_batch) != 30:
        logging.debug("Invalid batch size or empty request data")
        return jsonify({"error": "Batch size must be exactly 30 data points"}), 400

    try:
        normalized_data = preprocess_data(data_batch)
        flattened_data = normalized_data.reshape(-1, normalized_data.shape[2])
        pca_features = pca_model.transform(flattened_data)
        rul_predictions = gbr_model.predict(pca_features)
        return jsonify({"rul_predictions": rul_predictions.tolist()})
    except Exception as e:
        logging.error(f"Error during RUL prediction: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/history", methods=["GET"])
def get_history():
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    try:
        cur.execute(
            "SELECT timestamp, mse, classification, rul_estimate "
            "FROM predictions ORDER BY timestamp DESC LIMIT %s OFFSET %s",
            (limit, offset)
        )
        history_data = cur.fetchall()
        return jsonify(history_data)
    except Exception as e:
        conn.rollback()
        logging.error(f"Error retrieving history: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/")
def dashboard():
    return render_template("index.html")


# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
