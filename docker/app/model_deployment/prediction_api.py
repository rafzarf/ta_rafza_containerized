import os
from flask import Flask, request, jsonify
import numpy as np
from tensorflow.keras.models import load_model

app = Flask(__name__)

# Load the LSTM model for anomaly detection
model = load_model('lstm_autoencoder.h5')

@app.route('/predict', methods=['POST'])
def predict():
    data = request.json.get('data')
    if data is None:
        return jsonify({"error": "No data provided"}), 400

    try:
        prediction = model.predict(np.array([data]))
        anomaly_score = np.mean(np.square(data - prediction))  # Mean squared error as anomaly score
        return jsonify({'anomaly_score': anomaly_score})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.getenv('FLASK_PREDICTION_PORT', 5001)))
