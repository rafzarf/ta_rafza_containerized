import matplotlib.pyplot as plt

# Plot training MSE distribution to visualize the threshold
plt.figure(figsize=(10, 5))
plt.hist(train_mse, bins=50, alpha=0.7, label='Training MSE')
plt.axvline(model_threshold, color='red', linestyle='--', label='Model Threshold (95th Percentile)')
plt.title('Distribution of Training Reconstruction Error (MSE)')
plt.xlabel('MSE')
plt.ylabel('Frequency')
plt.legend()
plt.show()

# Plot test MSE with ISO classifications
plt.figure(figsize=(12, 6))
plt.plot(test_mse, label="Test Reconstruction Error (MSE)")
plt.axhline(y=iso_class_I_thresholds["A (Good)"], color='green', linestyle='--', label="ISO A (Good)")
plt.axhline(y=iso_class_I_thresholds["B (Acceptable)"], color='yellow', linestyle='--', label="ISO B (Acceptable)")
plt.axhline(y=iso_class_I_thresholds["C (Alert)"], color='orange', linestyle='--', label="ISO C (Alert)")
plt.axhline(y=iso_class_I_thresholds["D (Not Allowed)"], color='red', linestyle='--', label="ISO D (Not Allowed)")
plt.xlabel("Time Step")
plt.ylabel("MSE")
plt.legend()
plt.title("Test Data Reconstruction Error with ISO Thresholds")
plt.show()
