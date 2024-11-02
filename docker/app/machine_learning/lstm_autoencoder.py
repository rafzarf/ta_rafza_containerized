import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Model
from tensorflow.keras.layers import LSTM, RepeatVector, TimeDistributed, Dense, Input
import matplotlib.pyplot as plt

# Generate synthetic time-series data for demonstration
def generate_synthetic_data(samples=1000, timesteps=30, features=3):
    # Create random data for demonstration
    data = np.random.random((samples, timesteps, features))
    return data

# Step 1: Create an LSTM Autoencoder Model
def create_lstm_autoencoder(timesteps, features):
    # Encoder
    input_layer = Input(shape=(timesteps, features))
    encoded = LSTM(64, activation='relu', return_sequences=False)(input_layer)
    
    # Repeat vector to reshape for decoder input
    repeat_vector = RepeatVector(timesteps)(encoded)
    
    # Decoder
    decoded = LSTM(64, activation='relu', return_sequences=True)(repeat_vector)
    output_layer = TimeDistributed(Dense(features))(decoded)
    
    # Autoencoder model
    autoencoder = Model(inputs=input_layer, outputs=output_layer)
    autoencoder.compile(optimizer='adam', loss='mse')
    return autoencoder

# Step 2: Prepare Data
timesteps = 30  # Number of time steps in each sample
features = 3    # Number of features (e.g., x, y, z axes)
data = generate_synthetic_data(samples=1000, timesteps=timesteps, features=features)

# Step 3: Train-Test Split
split = int(0.8 * len(data))
train_data = data[:split]
test_data = data[split:]

# Step 4: Train the Model
autoencoder = create_lstm_autoencoder(timesteps, features)
history = autoencoder.fit(train_data, train_data, epochs=50, batch_size=32, validation_split=0.2, verbose=1)

# Step 5: Plot Training Loss
plt.plot(history.history['loss'], label='Training Loss')
plt.plot(history.history['val_loss'], label='Validation Loss')
plt.legend()
plt.show()

# Step 6: Evaluate Reconstruction Error
reconstructed = autoencoder.predict(test_data)
mse = np.mean(np.power(test_data - reconstructed, 2), axis=(1, 2))

# Step 7: Set an Anomaly Detection Threshold
threshold = np.percentile(mse, 95)  # Set threshold based on a percentile of MSE
print(f"Anomaly Detection Threshold: {threshold}")

# Step 8: Identify Anomalies
anomalies = mse > threshold
print(f"Number of anomalies detected: {np.sum(anomalies)}")

# Visualize Anomaly Scores
plt.hist(mse, bins=50)
plt.axvline(threshold, color='red', linestyle='--')
plt.title("Reconstruction Error")
plt.xlabel("MSE")
plt.ylabel("Frequency")
plt.show()
