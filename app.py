import os
import time
import threading
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, Response, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import cv2
import face_recognition
import numpy as np

from config import settings
from alerts.twilio_notifier import notifier

app = Flask(__name__)

# Global variables for background camera streaming
latest_processed_frame = None
camera_running = False
camera_thread = None
frame_lock = threading.Lock()
last_heartbeat_time = 0.0

# Face recognition database
known_face_encodings = []
known_face_names = []
db_lock = threading.Lock()

def load_known_faces():
    """
    Loads known face images and computes encodings.
    """
    global known_face_encodings, known_face_names
    
    encodings_temp = []
    names_temp = []
    supported_extensions = {".jpg", ".jpeg", ".png"}
    
    print("[INFO] Reloading known face database...")
    if not settings.KNOWN_FACES_DIR.exists():
        settings.KNOWN_FACES_DIR.mkdir(parents=True, exist_ok=True)
        
    image_files = [
        f for f in settings.KNOWN_FACES_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in supported_extensions
    ]
    
    for file_path in image_files:
        name = file_path.stem.replace("_", " ").title()
        try:
            image = face_recognition.load_image_file(str(file_path))
            encodings = face_recognition.face_encodings(image)
            if len(encodings) > 0:
                encodings_temp.append(encodings[0])
                names_temp.append(name)
                print(f"[INFO] Loaded known face: {name}")
        except Exception as e:
            print(f"[ERROR] Failed to load {file_path.name}: {e}")
            
    with db_lock:
        known_face_encodings = encodings_temp
        known_face_names = names_temp
        
    print(f"[INFO] Reload complete. Active entries: {len(known_face_encodings)}")

def background_camera_worker():
    """
    Background worker thread that connects to the camera source,
    performs face recognition, draws annotations, raises alerts,
    and updates the latest processed frame.
    """
    global latest_processed_frame, camera_running, last_heartbeat_time
    
    last_alert_time = 0
    last_capture_time = 0
    video_capture = None
    current_source = None
    
    # Pre-load known face databases
    load_known_faces()
    
    print("[INFO] Camera background thread started.")
    camera_running = True
    process_this_frame = True
    
    # Face locations/encodings variables
    face_locations = []
    face_encodings = []
    face_names = []
    
    while camera_running:
        # Check for user activity timeout (Webcam Mode)
        if settings.get_effective_camera_mode() == "webcam":
            if time.time() - last_heartbeat_time > 6.0:  # 6-second inactivity threshold
                print("[INFO] No active users detected (heartbeat timeout). Stopping webcam stream.")
                camera_running = False
                break
        # Check if the video source changed in configurations (Hot-swapping cameras)
        if current_source != settings.VIDEO_SOURCE:
            if video_capture is not None:
                print(f"[INFO] Releasing camera source {current_source} due to source hot-swap.")
                video_capture.release()
                video_capture = None
            
            current_source = settings.VIDEO_SOURCE
            print(f"[INFO] Connecting to camera source: {current_source}")
            video_capture = cv2.VideoCapture(current_source)
            # Short delay to allow network camera buffers to initialize
            time.sleep(1.0)
            
        if video_capture is None or not video_capture.isOpened():
            print(f"[WARNING] Waiting for camera source {current_source} to become available...")
            video_capture = cv2.VideoCapture(current_source)
            time.sleep(2.0)
            continue
            
        ret, frame = video_capture.read()
        if not ret:
            print("[WARNING] Failed to grab frame from source. Re-trying...")
            time.sleep(0.5)
            continue
            
        # Process and recognize faces
        if process_this_frame:
            # Resize frame to 1/4 size for faster processing
            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            # Convert color from BGR to RGB
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            
            face_locations = face_recognition.face_locations(rgb_small_frame)
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
            
            face_names = []
            with db_lock:
                for face_encoding in face_encodings:
                    name = "Unknown"
                    if known_face_encodings:
                        matches = face_recognition.compare_faces(
                            known_face_encodings, 
                            face_encoding, 
                            tolerance=settings.TOLERANCE
                        )
                        face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                        
                        if len(face_distances) > 0:
                            best_match_index = np.argmin(face_distances)
                            if matches[best_match_index]:
                                name = known_face_names[best_match_index]
                                
                    face_names.append(name)
                    
        process_this_frame = not process_this_frame
        
        # Check for unknown intruders
        unknown_detected = False
        
        # Draw bounding boxes and labels
        for (top, right, bottom, left), name in zip(face_locations, face_names):
            top *= 4
            right *= 4
            bottom *= 4
            left *= 4
            
            if name == "Unknown":
                color = (0, 0, 255)  # Red BGR
                unknown_detected = True
            else:
                color = (0, 255, 0)  # Green BGR
                
            # Face box
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            # Label background box
            cv2.rectangle(frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED)
            font = cv2.FONT_HERSHEY_DUPLEX
            cv2.putText(frame, name, (left + 6, bottom - 10), font, 0.75, (255, 255, 255), 1)
            
        # Intruder notification triggers
        if unknown_detected:
            now_time = time.time()
            if now_time - last_capture_time >= settings.CAPTURE_COOLDOWN_SECONDS:
                now_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                photo_name = f"captured_unknown_{now_str}.jpg"
                photo_path = settings.CAPTURED_DIR / photo_name
                
                try:
                    cv2.imwrite(str(photo_path), frame)
                    print(f"[ALERT] Unknown face captured: {photo_path}")
                    last_capture_time = now_time
                    
                    if now_time - last_alert_time >= settings.COOLDOWN_SECONDS:
                        time_display = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        notifier.send_alert(time_display, photo_name)
                        last_alert_time = now_time
                except Exception as e:
                    print(f"[ERROR] Failed to save/alert intruder details: {e}")
                    
        # Encode output frame as JPEG
        ret, jpeg = cv2.imencode('.jpg', frame)
        if ret:
            with frame_lock:
                latest_processed_frame = jpeg.tobytes()
                
        # Slight sleep to control CPU and match webcam frame-rate (approx 30fps)
        time.sleep(0.01)
        
    if video_capture is not None:
        video_capture.release()
    print("[INFO] Camera background thread stopped.")

def start_background_thread():
    """
    Initializes and starts the camera worker thread.
    """
    global camera_thread, camera_running
    if camera_thread is None or not camera_thread.is_alive():
        camera_running = True
        camera_thread = threading.Thread(target=background_camera_worker)
        camera_thread.daemon = True
        camera_thread.start()

# --- Flask Server Routing ---

@app.route('/')
def index():
    """
    Serves main user dashboard web interface.
    """
    global last_heartbeat_time
    # Reset heartbeat and ensure thread is running
    if settings.get_effective_camera_mode() == "webcam":
        last_heartbeat_time = time.time()
    start_background_thread()
    return render_template("index.html")

def yield_frames():
    """
    Helper generator that returns MJPEG boundary frames.
    """
    while camera_running:
        with frame_lock:
            frame_bytes = latest_processed_frame
            
        if frame_bytes is None:
            time.sleep(0.1)
            continue
            
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.03)  # limit yield to ~30 FPS

@app.route('/video_feed')
def video_feed():
    """
    Flask route serving the processed camera MJPEG stream.
    """
    global last_heartbeat_time
    if settings.get_effective_camera_mode() == "webcam":
        last_heartbeat_time = time.time()
        start_background_thread()
    return Response(yield_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/heartbeat', methods=['POST'])
def api_heartbeat():
    """
    Heartbeat ping from frontend to signal active tab.
    In Webcam Mode, automatically starts camera background loop if inactive.
    """
    global last_heartbeat_time
    last_heartbeat_time = time.time()
    
    effective_mode = settings.get_effective_camera_mode()
    started = False
    if effective_mode == "webcam":
        if not camera_running or camera_thread is None or not camera_thread.is_alive():
            print("[INFO] Heartbeat received. Re-starting webcam stream.")
            start_background_thread()
            started = True
            
    return jsonify({
        "status": "success",
        "camera_running": camera_running,
        "effective_mode": effective_mode,
        "started": started
    })

@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    """
    API endpoint to retrieve or update system configurations.
    """
    if request.method == 'GET':
        return jsonify({
            "VIDEO_SOURCE": settings.VIDEO_SOURCE,
            "CAMERA_MODE": settings.CAMERA_MODE,
            "TOLERANCE": settings.TOLERANCE,
            "COOLDOWN_SECONDS": settings.COOLDOWN_SECONDS,
            "CAPTURE_COOLDOWN_SECONDS": settings.CAPTURE_COOLDOWN_SECONDS,
            "TWILIO_ACCOUNT_SID": settings.TWILIO_ACCOUNT_SID,
            "TWILIO_AUTH_TOKEN": settings.TWILIO_AUTH_TOKEN,
            "TWILIO_FROM_NUMBER": settings.TWILIO_FROM_NUMBER,
            "TO_NUMBER": settings.TO_NUMBER
        })
        
    elif request.method == 'POST':
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request body"}), 400
            
        try:
            # Save settings using settings.py helper
            settings.save_settings(data)
            
            # Hot-swap/Restart background thread based on mode updates
            effective_mode = settings.get_effective_camera_mode()
            if effective_mode == "cctv":
                start_background_thread()
            elif effective_mode == "webcam":
                global last_heartbeat_time
                last_heartbeat_time = time.time()
                start_background_thread()
                
            return jsonify({"status": "success", "message": "Settings updated successfully."})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def api_upload():
    """
    Registers a new authorized face to known_faces/ folder and re-runs encoding.
    """
    name = request.form.get("name")
    photo = request.files.get("photo")
    
    if not name or not photo:
        return jsonify({"error": "Missing required name or photo file."}), 400
        
    # Clean up name for file system usage (e.g. John Doe -> john_doe)
    clean_name = secure_filename(name.lower().replace(" ", "_"))
    extension = Path(photo.filename).suffix.lower()
    
    if extension not in {'.jpg', '.jpeg', '.png'}:
        return jsonify({"error": "Invalid file format. Upload JPG or PNG."}), 400
        
    filename = f"{clean_name}{extension}"
    target_path = settings.KNOWN_FACES_DIR / filename
    
    try:
        photo.save(str(target_path))
        # Verify the saved image has at least one face before loading it
        temp_image = face_recognition.load_image_file(str(target_path))
        encodings = face_recognition.face_encodings(temp_image)
        
        if len(encodings) == 0:
            # Delete invalid image
            os.remove(target_path)
            return jsonify({"error": "Could not detect any face in the uploaded image. Please try another photo."}), 400
            
        # Face is valid, reload database on background worker
        load_known_faces()
        return jsonify({"status": "success", "name": name, "file": filename})
        
    except Exception as e:
        if target_path.exists():
            os.remove(target_path)
        return jsonify({"error": f"Failed to register face: {e}"}), 500

@app.route('/api/captured')
def api_captured():
    """
    Retrieves list of captured intruder logs.
    """
    logs = []
    supported_extensions = {".jpg", ".jpeg", ".png"}
    
    if settings.CAPTURED_DIR.exists():
        for file_path in settings.CAPTURED_DIR.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                # Extract clean date from captured_unknown_YYYY-MM-DD_HH-MM-SS.jpg
                timestamp = file_path.stem.replace("captured_unknown_", "")
                logs.append({
                    "filename": file_path.name,
                    "timestamp": timestamp,
                    "url": f"/captured_photos/{file_path.name}"
                })
                
    return jsonify(logs)

@app.route('/captured_photos/<filename>')
def captured_photos(filename):
    """
    Static route serving saved photos from captured/ directory.
    """
    return send_from_directory(settings.CAPTURED_DIR, filename)

if __name__ == "__main__":
    # In CCTV mode, start background processing immediately at boot.
    # In Webcam mode, load faces but wait for dashboard/heartbeats to activate camera.
    if settings.get_effective_camera_mode() == "cctv":
        start_background_thread()
    else:
        load_known_faces()
        
    # Start web server
    print("[INFO] Starting Flask web dashboard on port 5000...")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
