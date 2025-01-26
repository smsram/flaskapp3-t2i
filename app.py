from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from io import BytesIO
import requests
from threading import Lock
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Allow all origins for simplicity

API_KEY = os.getenv('HUGGINGFACE_API_KEY')

if not API_KEY:
    raise ValueError("API key is not set in environment variables")

MAX_TRAFFIC = 3
current_traffic = 0
traffic_lock = Lock()  # Lock for thread safety

@app.route('/generate-image', methods=['POST'])
def generate_image():
    global current_traffic
    try:
        with traffic_lock:
            if current_traffic >= MAX_TRAFFIC:
                return jsonify({
                    'error': 'Server is busy. Please try again later.',
                    'traffic': f"{current_traffic}/{MAX_TRAFFIC}"
                }), 429
            current_traffic += 1

        data = request.get_json()
        prompt = data.get('prompt')

        if not prompt:
            return jsonify({'error': 'Prompt is required', 'traffic': f"{current_traffic}/{MAX_TRAFFIC}"}), 400

        image_data = generate_image_from_huggingface(prompt)

        if not image_data:
            return jsonify({'error': 'Failed to generate image', 'traffic': f"{current_traffic}/{MAX_TRAFFIC}"}), 500

        image_stream = BytesIO(image_data)
        image_stream.seek(0)

        response = send_file(image_stream, mimetype='image/png')
        response.cache_control.no_cache = True
        response.cache_control.no_store = True
        response.cache_control.must_revalidate = True
        response.headers['X-Traffic-Ratio'] = f"{current_traffic}/{MAX_TRAFFIC}"
        return response

    except Exception as e:
        print("Error while generating image:", e)
        return jsonify({'error': str(e), 'traffic': f"{current_traffic}/{MAX_TRAFFIC}"}), 500

    finally:
        with traffic_lock:
            current_traffic -= 1

@app.route('/traffic', methods=['GET'])
def get_traffic():
    global current_traffic
    with traffic_lock:
        return jsonify({'traffic': f"{current_traffic}/{MAX_TRAFFIC}"})

def generate_image_from_huggingface(prompt):
    try:
        API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-3.5-large"
        headers = {"Authorization": f"Bearer {API_KEY}"}
        data = {"inputs": prompt}

        response = requests.post(API_URL, headers=headers, json=data)

        if response.status_code != 200:
            print(f"Hugging Face API error: {response.status_code}, {response.text}")
            return None

        return response.content

    except requests.exceptions.RequestException as e:
        print("Request to Hugging Face API failed:", e)
        return None

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
