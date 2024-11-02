import numpy as np
import tensorflow as tf
from flask import Flask, jsonify, request
import json

# Initialize the Flask app
app = Flask(__name__)

# Load the trained LSTM Autoencoder model
model_path = 'path/to/your/lstm_autoencoder_model.h5'
autoencoder = tf.keras.models.load_model(model_path)

# Set an anomaly detection threshold (based on training set analysis)
threshold = 0.02  # Adjust this based on your model's performance and use case

# Function to preprocess the input data
def preprocess_input(data, timesteps=30, features=3):
    """
    Preprocesses input data for the LSTM Autoencoder model.
    :param data: List or array of input sensor data.
    :param timesteps: Number of time steps expected by the model.
    :param features: Number of features expected by the model.
    :return: Numpy array reshaped for model prediction.
    """
    data = np.array(data).reshape(1, timesteps, features)  # Adjust shape to (1, timesteps, features)
    return data

# Flask route for anomaly detection inference
@app.route('/predict-anomaly', methods=['POST'])
def predict_anomaly():
    try:
        # Parse input data from the POST request
        input_data = request.json.get('sensor_data')
        
        # Ensure input data is in the correct format
        if not input_data or len(input_data) != 30 or len(input_data[0]) != 3:
            return jsonify({"error": "Invalid input data format. Expected shape (30, 3)"}), 400
        
        # Preprocess the input data
        processed_data = preprocess_input(input_data)
        
        # Make predictions (reconstruct the input)
        reconstructed = autoencoder.predict(processed_data)
        
        # Calculate reconstruction error (MSE)
        mse = np.mean(np.power(processed_data - reconstructed, 2), axis=(1, 2))
        
        # Determine if input data is an anomaly
        is_anomaly = mse[0] > threshold
        result = {
            "reconstruction_error": mse[0],
            "is_anomaly": is_anomaly,
            "threshold": threshold
        }
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Run the Flask app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
