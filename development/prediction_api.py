import os
from flask import Flask, request, jsonify
import numpy as np
from tensorflow.keras.models import load_model

app = Flask(__name__)

# Load the model when the Flask app starts
model = None

def load_model_from_file():
    global model
    model = load_model('lstm_autoencoder.h5')

@app.route('/')
def home():
    return jsonify(message="Prediction API is running!")

@app.route('/predict', methods=['POST'])
def predict():
    global model
    if model is None:
        load_model_from_file()
    data = request.json['data']
    prediction = model.predict(np.array([data]))
    return jsonify({'prediction': prediction.tolist()})

if __name__ == '__main__':
    load_model_from_file()  # Load the model when the app starts
    prediction_port = int(os.environ.get('FLASK_PREDICTION_PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=prediction_port)
