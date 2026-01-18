# app.py
from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
import cv2
import threading
import time
import base64

# Import Modules
from vision import VisionTriage 
from services import TriageService, PatientManager

# Auth0
import json
from os import environ as env
from urllib.parse import quote_plus, urlencode
from authlib.integrations.flask_client import OAuth
from dotenv import find_dotenv, load_dotenv
from flask import Flask, redirect, render_template, session, url_for

app = Flask(__name__)
app.secret_key = env.get("AUTH0_SECRET")
CORS(app)

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

# --- CONFIGURATION ---
CAM_SOURCES = {
    1: "http://10.102.199.32:4747/video",  # Camera 1
    2: "http://10.215.39.34:4747/video"   # Camera 2
}


oauth = OAuth(app)

oauth.register(
    "auth0",
    client_id=env.get("AUTH0_CLIENT_ID"),
    client_secret=env.get("AUTH0_CLIENT_SECRET"),
    client_kwargs={
        "scope": "openid profile email",
    },
    server_metadata_url=f'https://{env.get("AUTH0_DOMAIN")}/.well-known/openid-configuration'
)

# --- GLOBAL STATE ---
patient_mgr = PatientManager()
triage_service = TriageService()

# Dictionary to hold state for each camera: { id: { 'frame': None, 'lock': Lock() } }
STREAMS = {}
for cam_id in CAM_SOURCES:
    STREAMS[cam_id] = {
        'frame': None,
        'lock': threading.Lock()
    }

def camera_worker(cam_id, url):
    """
    Dedicated thread for a single camera.
    Instantiates its own VisionTriage to avoid threading conflicts.
    """
    print(f"[{cam_id}] Connecting to {url}...")
    
    # 1. Instantiate Vision Model (Thread-Local)
    vision_system = VisionTriage()
    cap = cv2.VideoCapture(url)
    
    # Reconnection / Loop logic
    while True:
        if not cap.isOpened():
            cap.open(url)
            time.sleep(2)
            continue

        success, frame = cap.read()
        if not success:
            # If stream drops, keep retrying
            time.sleep(0.1)
            continue

        # 2. Run Vision Analysis
        try:
            annotated_frame, alert = vision_system.analyze_frame(frame)
        except Exception as e:
            print(f"[{cam_id}] Vision Error: {e}")
            annotated_frame = frame
            alert = None

        # 3. Handle "Code Black" Logic
        if alert:
            active_patients = patient_mgr.get_active()
            last_complaint = active_patients[-1]['complaint'] if active_patients else ""
            
            # De-duplication: Ensure we don't spam the same alert
            alert_msg = f"CODE BLACK (CAM {cam_id}): {alert}"
            
            if alert_msg not in last_complaint:
                print(f"🚨 CAM {cam_id} DETECTED: {alert}")
                
                # Convert to base64 for snapshot
                _, buffer = cv2.imencode('.jpg', annotated_frame)
                b64_img = base64.b64encode(buffer).decode('utf-8')
                
                patient_mgr.add_patient(
                    name=f"Unknown (Cam {cam_id})",
                    age="N/A",
                    complaint=alert_msg,
                    esi=0, 
                    analysis=f"**VISUAL OVERRIDE:** Camera {cam_id} detected {alert}.",
                    source_docs=[],
                    snapshot=f"data:image/jpeg;base64,{b64_img}"
                )

        # 4. Update Global State safely
        with STREAMS[cam_id]['lock']:
            STREAMS[cam_id]['frame'] = annotated_frame.copy()
            
        time.sleep(0.03) # Cap ~30 FPS per thread
    # return 

# --- START THREADS ---
# Spin up a thread for each camera source
for cam_id, url in CAM_SOURCES.items():
    t = threading.Thread(target=camera_worker, args=(cam_id, url), daemon=True)
    t.start()

# --- ROUTES ---

@app.route('/')
def index():
    """Renders the main single-page UI."""
    return render_template('index.html')

@app.route('/video_feed/<int:cam_id>')
def video_feed(cam_id):
    """Streams the specific camera feed via MJPEG."""
    if cam_id not in STREAMS:
        return "Camera not found", 404

    def generate(c_id):
        stream_data = STREAMS[c_id]
        while True:
            with stream_data['lock']:
                if stream_data['frame'] is None:
                    time.sleep(0.1)
                    continue
                
                # Encode frame
                (flag, encodedImage) = cv2.imencode(".jpg", stream_data['frame'])
                if not flag:
                    continue
            
            # Yield MJPEG chunk
            yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
                  bytearray(encodedImage) + b'\r\n')
            time.sleep(0.05)

    return Response(generate(cam_id), mimetype="multipart/x-mixed-replace; boundary=frame")

# --- API ENDPOINTS ---

@app.route('/api/submit', methods=['POST'])
def submit_patient():
    data = request.json
    esi, analysis, docs = triage_service.analyze(data['age'], data['complaint'])
    
    patient_mgr.add_patient(
        name=data['name'],
        age=data['age'],
        complaint=data['complaint'],
        esi=esi,
        analysis=analysis,
        source_docs=docs
    )
    return jsonify({"status": "success", "esi": esi})

@app.route('/api/queue', methods=['GET'])
def get_queue():
    return jsonify(patient_mgr.get_all())

@app.route('/api/complete/<id>', methods=['POST'])
def complete_patient(id):
    success = patient_mgr.mark_done(id)
    return jsonify({"success": success})

# Auth0
@app.route("/login")
def login():
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for("callback", _external=True)
    )

@app.route("/callback", methods=["GET", "POST"])
def callback():
    token = oauth.auth0.authorize_access_token()
    session["user"] = token
    return redirect("/")

@app.route("/session")
def session_info():
    return {
        "logged_in": "user" in session
    }

@app.route("/logout")
def logout():
    session.clear()
    return redirect(
        "https://" + env.get("AUTH0_DOMAIN")
        + "/v2/logout?"
        + urlencode(
            {
                "returnTo": url_for("index", _external=True),
                "client_id": env.get("AUTH0_CLIENT_ID"),
            },
            quote_via=quote_plus,
        )
    )

if __name__ == '__main__':
    # Threaded=True is important for Flask to handle multiple requests (video streams) at once
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)