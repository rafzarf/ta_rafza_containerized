import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler

# Example data preparation
# Load your real data here and preprocess it
X = np.random.rand(1000, 30, 3)  # Replace with actual input data (samples, timesteps, features)
anomaly_scores = np.random.rand(1000, 1)  # Replace with actual anomaly scores
rul = np.random.randint(10, 100, 1000)  # Replace with actual RUL labels

# Combine sensor data and anomaly scores into one dataset
X_combined = np.concatenate([X, anomaly_scores.reshape(-1, 1, 1)], axis=2)

# Split data into training and testing sets
X_train, X_test, y_train, y_test = train_test_split(X_combined, rul, test_size=0.2, random_state=42)

# Scale the RUL target variable (optional but recommended)
scaler = MinMaxScaler()
y_train_scaled = scaler.fit_transform(y_train.reshape(-1, 1))
y_test_scaled = scaler.transform(y_test.reshape(-1, 1))

# Build the LSTM model for RUL prediction
model = Sequential()
model.add(LSTM(64, input_shape=(X_train.shape[1], X_train.shape[2]), return_sequences=True))
model.add(Dropout(0.2))
model.add(LSTM(32, return_sequences=False))
model.add(Dropout(0.2))
model.add(Dense(1))  # Output layer for RUL prediction

model.compile(optimizer='adam', loss='mean_squared_error')

# Train the model
history = model.fit(X_train, y_train_scaled, epochs=50, batch_size=32, validation_split=0.2, verbose=1)

# Evaluate the model on test data
y_pred_scaled = model.predict(X_test)
y_pred = scaler.inverse_transform(y_pred_scaled)  # Convert predictions back to original scale

# Print and analyze results
print("Predicted RUL:", y_pred[:10])
print("Actual RUL:", y_test[:10])
