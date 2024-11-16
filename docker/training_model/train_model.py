import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential, Model
from tensorflow.keras.layers import LSTM, Dense, RepeatVector, TimeDistributed, Dropout
from tensorflow.keras.regularizers import L2
from tensorflow.keras.callbacks import EarlyStopping
import matplotlib.pyplot as plt

# Load and preprocess data
data = pd.read_csv("/content/processed_data_with_RUL (1).csv")
numeric_columns = data.select_dtypes(include=[np.number]).columns
data[numeric_columns] = data[numeric_columns].fillna(data[numeric_columns].mean())
scaler = MinMaxScaler()
feature_columns = data.drop(columns=["time", "RUL"]).columns
data[feature_columns] = scaler.fit_transform(data[feature_columns])

# Prepare sequences (e.g., 30 time steps per sequence) for the Autoencoder
sequence_length = 30
X = []

for i in range(len(data) - sequence_length):
    X.append(data[feature_columns].iloc[i:i + sequence_length].values)

X = np.array(X)

# Split into train and test sets
split_index = int(0.8 * len(X))
X_train, X_test = X[:split_index], X[split_index:]

# Define the LSTM Autoencoder model with additional Dropout and L2 regularization
model = Sequential([
    LSTM(64, activation='relu', input_shape=(X_train.shape[1], X_train.shape[2]),
         return_sequences=True, kernel_regularizer=L2(0.001)),
    Dropout(0.3),

    LSTM(32, activation='relu', return_sequences=False, kernel_regularizer=L2(0.001)),
    Dropout(0.3),

    RepeatVector(X_train.shape[1]),

    LSTM(32, activation='relu', return_sequences=True, kernel_regularizer=L2(0.001)),
    Dropout(0.3),

    LSTM(64, activation='relu', return_sequences=True, kernel_regularizer=L2(0.001)),
    Dropout(0.3),

    TimeDistributed(Dense(X_train.shape[2], kernel_regularizer=L2(0.001)))
])

# Compile model
model.compile(optimizer='adam', loss='mse')

# Use early stopping to avoid overfitting
early_stopping = EarlyStopping(monitor="val_loss", patience=10, restore_best_weights=True)

# Train the model with early stopping
history = model.fit(X_train, X_train, epochs=50, batch_size=32, validation_split=0.1,
                    callbacks=[early_stopping], verbose=1)

# Plot training history
plt.plot(history.history["loss"], label="Train Loss")
plt.plot(history.history["val_loss"], label="Validation Loss")
plt.title("Model Loss During Training with Dropout and Early Stopping")
plt.xlabel("Epochs")
plt.ylabel("Loss")
plt.legend()
plt.show()

# Save model in a flexible format for inference
model.save("lstm_autoencoder_model_compatible.h5")

# Step 1: Calculate the reconstruction error on training data
X_train_pred = model.predict(X_train)
train_mse = np.mean(np.square(X_train - X_train_pred), axis=(1, 2))

# Set a base anomaly threshold using model-based statistics (e.g., 95th percentile of training error)
model_threshold = np.percentile(train_mse, 95)

# Step 2: Define ISO 2372 Class I thresholds from the updated table
iso_class_I_thresholds = {
    "A (Good)": 0.71,
    "B (Acceptable)": 1.8,
    "C (Alert)": 4.5,
    "D (Not Allowed)": np.inf
}

# Step 3: Set anomaly threshold directly to the ISO Class I "Alert" level
anomaly_threshold = iso_class_I_thresholds["C (Alert)"]
print(f"Final Anomaly Threshold set to ISO Class I 'Alert': {anomaly_threshold}")


# Step 4: Apply threshold during evaluation on test data
X_test_pred = model.predict(X_test)
test_mse = np.mean(np.square(X_test - X_test_pred), axis=(1, 2))

# Step 5: Classify each reconstruction error according to ISO classes
def classify_iso(error, iso_thresholds):
    if error <= iso_thresholds["A (Good)"]:
        return "A (Good)"
    elif error <= iso_thresholds["B (Acceptable)"]:
        return "B (Acceptable)"
    elif error <= iso_thresholds["C (Alert)"]:
        return "C (Alert)"
    else:
        return "D (Not Allowed)"

# Apply classification to test MSE based on ISO thresholds
iso_classification = [classify_iso(error, iso_class_I_thresholds) for error in test_mse]

# Step 6: Plot reconstruction error with ISO classifications
plt.figure(figsize=(12, 6))
plt.plot(test_mse, label="Reconstruction Error")
plt.axhline(y=iso_class_I_thresholds["A (Good)"], color='green', linestyle='--', label="ISO A (Good)")
plt.axhline(y=iso_class_I_thresholds["B (Acceptable)"], color='yellow', linestyle='--', label="ISO B (Acceptable)")
plt.axhline(y=iso_class_I_thresholds["C (Alert)"], color='orange', linestyle='--', label="ISO C (Alert)")
plt.axhline(y=iso_class_I_thresholds["D (Not Allowed)"], color='red', linestyle='--', label="ISO D (Not Allowed)")
plt.xlabel("Time Step")
plt.ylabel("Reconstruction Error")
plt.legend()
plt.title("Reconstruction Error with ISO 2372 Class I Thresholds (with Dropout and Regularization)")
plt.show()

import tensorflow as tf

# Replace with the actual path to your model file
model_path = "/content/lstm_autoencoder_model.keras"
try:
    model = tf.keras.models.load_model(model_path)
    print("Model loaded successfully with TensorFlow version:", tf.__version__)
except Exception as e:
    print("Error loading model. This might indicate a version mismatch.")
    print("Error:", e)
