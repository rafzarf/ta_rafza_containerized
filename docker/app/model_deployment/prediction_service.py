import os
import numpy as np
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/predict', methods=['POST'])
def predict():
    data = request.json.get('data')
    if data is None:
        return jsonify({"error": "No data provided"}), 400

    try:
        # Placeholder: Simulate an anomaly score (to replace with real model later)
        anomaly_score = np.random.random()
        return jsonify({'anomaly_score': anomaly_score})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.getenv('FLASK_PREDICTION_PORT', 5001)))
