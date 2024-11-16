from flask import Flask, request, jsonify, render_template
import numpy as np
import tensorflow as tf
import logging
import joblib  # For loading the scaler
import psycopg2
import smtplib
from email.mime.text import MIMEText
from apscheduler.schedulers.background import BackgroundScheduler

# Initialize Flask app
app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Load the trained LSTM model
model = tf.keras.models.load_model("/home/rafzarf/Code/ta_rafza_containerized/docker/model_deployment/pretrained_model/lstm_autoencoder_model.keras")

# Load the scaler used during training
scaler = joblib.load("/home/rafzarf/Code/ta_rafza_containerized/docker/model_deployment/pretrained_model/scaler.save")  

# Email configuration
EMAIL_ADDRESS = "xxrafzaxx@gmail.com"
EMAIL_PASSWORD = "NaonAiKamu28"
ALERT_RECIPIENTS = ["xxrafzaxx@gmail.com"]

# Set up PostgreSQL connection
conn = psycopg2.connect(
    dbname="ta_rafza_db",
    user="rafzarf",
    password="Rf28012002@postgres",
    host="localhost"
)
cur = conn.cursor()

# Adjusted thresholds using the 95th percentile if needed
iso_class_I_thresholds = {
    "A (Good)": 0.71,
    "B (Acceptable)": max(1.12, 0.097),  # Example where we adjust based on the 95th percentile
    "C (Alert)": 1.8,
    "D (Not Allowed)": np.inf  # Upper limit
}


# Real-time feature expansion and scaling function
def preprocess_data(batch_data):
    processed_data = []
    
    for data in batch_data:
        x, y, z, acc = data["x"], data["y"], data["z"], data["acceleration"]
        magnitude = np.sqrt(x**2 + y**2 + z**2)
        
        # Calculate derived metrics
        processed_row = [
            acc, x, y, z, magnitude,
            acc, 0, x, 0, y, 0, z, 0, magnitude, 0,
            0,  # velocity placeholder
            0,  # acceleration change placeholder
            x / (magnitude + 1e-8), y / (magnitude + 1e-8), z / (magnitude + 1e-8),
            0, 0, 0, magnitude, magnitude  # cumulative, min, max placeholders
        ]
        
        processed_data.append(processed_row)
    
    # Convert to numpy array and apply scaler
    processed_data = np.array(processed_data)
    scaled_data = scaler.transform(processed_data)  # Use the loaded scaler for consistent scaling
    
    return scaled_data

# Estimate RUL based on MSE
def estimate_rul_percentage(mse):
    # Map MSE to RUL percentage (adjust these ranges as needed for accuracy)
    if mse <= iso_class_I_thresholds["A (Good)"]:
        return 100  # 100% RUL remaining
    elif mse <= iso_class_I_thresholds["B (Acceptable)"]:
        return 80  # 80% RUL remaining
    elif mse <= iso_class_I_thresholds["C (Alert)"]:
        return 50  # 50% RUL remaining
    else:
        return 20  # Critical - only 20% RUL remaining or less

def send_email_alert(mse, classification):
    if classification in ["C (Alert)", "D (Not Allowed)"]:  # Only alert for high anomalies
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
    cur.execute("SELECT COUNT(*) FROM predictions WHERE classification IN ('C (Alert)', 'D (Not Allowed)')")
    count = cur.fetchone()[0]
    
    # Send summary email
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


@app.route("/predict", methods=["POST"])
def predict():
    # Process incoming data
    data_batch = request.json
    if not data_batch or len(data_batch) != 30:
        app.logger.debug("Invalid batch size or empty request data")
        return jsonify({"error": "Batch size must be exactly 30 data points"}), 400

    try:
        # Preprocess data
        normalized_data = preprocess_data(data_batch)

        # Format for LSTM input
        sequence = normalized_data.reshape(1, 30, 25)

        # Run prediction and calculate MSE
        prediction = model.predict(sequence)
        mse = np.mean(np.square(sequence - prediction), axis=(1, 2))[0]

        # ISO classification
        if mse <= iso_class_I_thresholds["A (Good)"]:
            classification = "A (Good)"
        elif mse <= iso_class_I_thresholds["B (Acceptable)"]:
            classification = "B (Acceptable)"
        elif mse <= iso_class_I_thresholds["C (Alert)"]:
            classification = "C (Alert)"
        else:
            classification = "D (Not Allowed)"

        # Calculate RUL estimate
        rul_estimate = estimate_rul_percentage(mse)

        # Insert prediction and RUL estimate into database
        cur.execute(
            "INSERT INTO predictions (mse, classification, rul_estimate) VALUES (%s, %s, %s)",
            (mse, classification, rul_estimate)
        )
        conn.commit()

        # Respond with MSE, classification, and RUL estimate
        return jsonify({"mse": mse, "classification": classification, "rul_estimate": rul_estimate})

    except Exception as e:
        conn.rollback()  # Rollback the transaction on any error
        app.logger.error(f"Error during prediction: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/history", methods=["GET"])
def get_history():
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    try:
        # Retrieve data with RUL estimate
        cur.execute("SELECT timestamp, mse, classification, rul_estimate FROM predictions ORDER BY timestamp DESC LIMIT %s OFFSET %s", (limit, offset))
        history_data = cur.fetchall()
        return jsonify(history_data)

    except Exception as e:
        conn.rollback()  # Rollback the transaction on any error
        app.logger.error(f"Error retrieving history: {e}")
        return jsonify({"error": "Internal server error"}), 500




@app.route("/")
def dashboard():
    return render_template("index.html")


# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
