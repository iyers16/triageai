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

app = Flask(__name__)
CORS(app)

# --- GLOBAL STATE ---
# Instantiate Logic Classes
vision_system = VisionTriage()
patient_mgr = PatientManager()
triage_service = TriageService()

# Global variables for video streaming thread
output_frame = None
lock = threading.Lock()

def camera_loop():
    """Background thread for continuous video analysis."""
    global output_frame, lock
    cap = cv2.VideoCapture("http://10.102.199.32:4747/video")
    
    while True:
        success, frame = cap.read()
        if not success:
            time.sleep(0.1)
            continue

        # 1. Run Vision Analysis
        annotated_frame, alert = vision_system.analyze_frame(frame)
        
        # 2. Handle "Code Black" Logic (Server-Side)
        if alert:
            active_patients = patient_mgr.get_active()
            # De-duplication: Check last active patient
            last_complaint = active_patients[-1]['complaint'] if active_patients else ""
            
            if f"CODE BLACK: {alert}" not in last_complaint:
                print(f"🚨 DETECTED: {alert}")
                
                # Convert frame to base64 for storage/display in dashboard
                _, buffer = cv2.imencode('.jpg', annotated_frame)
                b64_img = base64.b64encode(buffer).decode('utf-8')
                
                patient_mgr.add_patient(
                    name="Unknown (Auto-Detected)",
                    age="N/A",
                    complaint=f"CODE BLACK: {alert}",
                    esi=0, 
                    analysis=f"**VISUAL OVERRIDE:** System detected {alert}.",
                    source_docs=[],
                    snapshot=f"data:image/jpeg;base64,{b64_img}"
                )

        # 3. Update global frame for streaming
        with lock:
            output_frame = annotated_frame.copy()
            
        time.sleep(0.03) # Cap at ~30 FPS

# Start the Camera Thread
t = threading.Thread(target=camera_loop, daemon=True)
t.start()

# --- ROUTES ---

@app.route('/')
def index():
    """Renders the main single-page UI."""
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    """Streams the video feed to the browser via MJPEG."""
    def generate():
        global output_frame, lock
        while True:
            with lock:
                if output_frame is None:
                    continue
                (flag, encodedImage) = cv2.imencode(".jpg", output_frame)
                if not flag:
                    continue
            yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
                  bytearray(encodedImage) + b'\r\n')
            time.sleep(0.05)
    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)