from flask import Flask, jsonify

# Initialize the Flask application
app = Flask(__name__)

# Define a simple route
@app.route('/')
def home():
    return jsonify(message="Hello from Flask mock app!")

# If this file is executed directly, run the Flask application
if __name__ == '__main__':
    # Use host 0.0.0.0 to ensure it's accessible outside the container
    app.run(host='0.0.0.0', port=5000)
