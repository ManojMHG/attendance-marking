from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os, json, base64, datetime, smtplib
import numpy as np
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash
import face_recognition
from io import BytesIO
from geopy.distance import geodesic  # For location checking

app = Flask(__name__, static_folder='../frontend', static_url_path='/')
CORS(app)

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
ATTENDANCE_FILE = os.path.join(DATA_DIR, 'attendance.xlsx')
NOTIF_FILE = os.path.join(DATA_DIR, 'notifications.txt')

# Owner security
OWNER_SECRET = os.getenv('OWNER_SECRET', 'owner-secret-change-me')
OWNER_EMAIL = os.getenv('OWNER_EMAIL')
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587')) if os.getenv('SMTP_PORT') else None
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')

# Face recognition threshold
THRESHOLD = float(os.getenv('FACE_THRESHOLD', '0.6'))

# Location restriction settings (CHANGE TO YOUR LOCATION OR USE ENV VARIABLES)
ALLOWED_LOCATION = (
    float(os.getenv('ALLOWED_LAT', '13.009649')),  # Default Hyderabad lat
    float(os.getenv('ALLOWED_LON', '77.637518'))   # Default Hyderabad lon
)
ALLOWED_RADIUS_METERS = int(os.getenv('ALLOWED_RADIUS', '10000'))  # Allowed radius in meters

def is_within_allowed_area(user_lat, user_lon):
    """Check if user's location is within allowed radius"""
    try:
        user_location = (float(user_lat), float(user_lon))
        distance = geodesic(user_location, ALLOWED_LOCATION).meters
        return distance <= ALLOWED_RADIUS_METERS
    except:
        return False

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, 'r') as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def decode_image_b64(data_uri):
    if ',' in data_uri:
        _, encoded = data_uri.split(',', 1)
    else:
        encoded = data_uri
    data = base64.b64decode(encoded)
    return face_recognition.load_image_file(BytesIO(data))

def send_owner_notification(text):
    timestamp = datetime.datetime.now().isoformat()
    msg_text = f"{timestamp} - {text}\n"
    try:
        if OWNER_EMAIL and SMTP_SERVER and SMTP_USER and SMTP_PASSWORD:
            message = f"Subject: Attendance System - Notification\n\n{msg_text}"
            if SMTP_PORT == 465:
                server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
            else:
                server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT or 587)
                server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [OWNER_EMAIL], message)
            server.quit()
        else:
            with open(NOTIF_FILE, 'a') as f:
                f.write(msg_text)
    except Exception as e:
        with open(NOTIF_FILE, 'a') as f:
            f.write(f"{timestamp} - NOTIFICATION ERROR: {str(e)}\n")

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json()
    required = ['id', 'password', 'domain', 'owner_secret', 'image', 'latitude', 'longitude']
    if not data or not all(k in data for k in required):
        return jsonify({'success': False, 'error': 'missing fields (required: id, password, domain, owner_secret, image, latitude, longitude)'}), 400

    # Location check
    if not is_within_allowed_area(data['latitude'], data['longitude']):
        return jsonify({'success': False, 'error': 'You are not in the allowed location for signup'}), 403

    if data['owner_secret'] != OWNER_SECRET:
        return jsonify({'success': False, 'error': 'invalid owner security value'}), 403

    uid = data['id']
    users = load_users()
    if uid in users:
        return jsonify({'success': False, 'error': 'id already exists'}), 400

    try:
        image = decode_image_b64(data['image'])
        encodings = face_recognition.face_encodings(image)
        if len(encodings) == 0:
            return jsonify({'success': False, 'error': 'no face detected in the provided image'}), 400
        encoding = encodings[0].tolist()
        pwd_hash = generate_password_hash(data['password'])
        users[uid] = {
            'password': pwd_hash,
            'domain': data['domain'],
            'encoding': encoding,
            'created_at': datetime.datetime.now().isoformat()
        }
        save_users(users)
        send_owner_notification(f"New account created: {uid} (domain: {data['domain']})")
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': f'exception: {str(e)}'}), 500

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    required = ['id', 'password', 'image', 'latitude', 'longitude']
    if not data or not all(k in data for k in required):
        return jsonify({'success': False, 'error': 'missing fields (required: id, password, image, latitude, longitude)'}), 400

    uid = data['id']
    users = load_users()
    if uid not in users:
        return jsonify({'success': False, 'error': 'user not found'}), 404

    if not check_password_hash(users[uid]['password'], data['password']):
        return jsonify({'success': False, 'error': 'invalid password'}), 401

    # Location check
    if not is_within_allowed_area(data['latitude'], data['longitude']):
        return jsonify({'success': False, 'error': 'You are not in the allowed location for attendance'}), 403

    try:
        image = decode_image_b64(data['image'])
        encodings = face_recognition.face_encodings(image)
        if len(encodings) == 0:
            return jsonify({'success': False, 'error': 'no face detected in the provided image'}), 400
        probe = encodings[0]
        stored = np.array(users[uid]['encoding'])
        dist = np.linalg.norm(stored - probe)
        recognized = float(dist) <= THRESHOLD

        if recognized:
            date = datetime.date.today().isoformat()
            time = datetime.datetime.now().strftime('%H:%M:%S')
            row = {'date': date, 'time': time, 'id': uid, 'domain': users[uid].get('domain', ''), 'status': 'present'}
            if os.path.exists(ATTENDANCE_FILE):
                df = pd.read_excel(ATTENDANCE_FILE)
                df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
            else:
                df = pd.DataFrame([row])
            df.to_excel(ATTENDANCE_FILE, index=False)

        return jsonify({'success': True, 'recognized': recognized, 'distance': float(dist)})
    except Exception as e:
        return jsonify({'success': False, 'error': f'exception: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
