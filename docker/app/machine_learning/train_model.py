import numpy as np
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, RepeatVector, TimeDistributed

def train_model():
    # Generate some example data
    X = np.random.randn(1000, 50, 1)

    model = Sequential([
        LSTM(32, activation='relu', input_shape=(50, 1), return_sequences=True),
        LSTM(16, activation='relu', return_sequences=False),
        RepeatVector(50),
        LSTM(16, activation='relu', return_sequences=True),
        LSTM(32, activation='relu', return_sequences=True),
        TimeDistributed(Dense(1))
    ])

    model.compile(optimizer='adam', loss='mse')
    model.fit(X, X, epochs=50, batch_size=32, validation_split=0.1)

    model.save('lstm_autoencoder.h5')
    print("Model trained and saved as 'lstm_autoencoder.h5'")

if __name__ == "__main__":
    train_model()
