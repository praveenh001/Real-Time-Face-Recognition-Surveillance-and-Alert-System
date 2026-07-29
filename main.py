import cv2
import face_recognition
import numpy as np
import os
import time
from datetime import datetime
from pathlib import Path

from config import settings
from alerts.twilio_notifier import notifier

def load_known_faces():
    """
    Loads images from the known_faces directory and computes their encodings.
    The filename (excluding extension) is used as the person's name.
    """
    known_face_encodings = []
    known_face_names = []
    
    supported_extensions = {".jpg", ".jpeg", ".png"}
    
    print("[INFO] Loading known faces...")
    if not settings.KNOWN_FACES_DIR.exists():
        print(f"[ERROR] Known faces directory '{settings.KNOWN_FACES_DIR}' does not exist.")
        return known_face_encodings, known_face_names
        
    image_files = [
        f for f in settings.KNOWN_FACES_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in supported_extensions
    ]
    
    if not image_files:
        print("[WARNING] No known faces found in the 'known_faces/' folder.")
        print("[WARNING] Put JPG/PNG images of authorized people in 'known_faces/' (e.g. 'john_doe.jpg').")
    
    for file_path in image_files:
        name = file_path.stem.replace("_", " ").title()
        print(f"[INFO] Loading image: {file_path.name} -> Name: {name}")
        try:
            image = face_recognition.load_image_file(str(file_path))
            encodings = face_recognition.face_encodings(image)
            
            if len(encodings) > 0:
                known_face_encodings.append(encodings[0])
                known_face_names.append(name)
                print(f"[INFO] Successfully encoded face for {name}")
            else:
                print(f"[WARNING] Could not find any face in {file_path.name}. Skipping this image.")
        except Exception as e:
            print(f"[ERROR] Failed to load/encode {file_path.name}: {e}")
            
    print(f"[INFO] Load complete. Loaded {len(known_face_encodings)} known face(s).")
    return known_face_encodings, known_face_names

def main():
    # Load face databases
    known_face_encodings, known_face_names = load_known_faces()
    
    # Track cooldown timer
    last_alert_time = 0
    last_capture_time = 0
    
    # Initialize camera source
    video_source = settings.VIDEO_SOURCE
    print(f"[INFO] Attempting to open video source: {video_source}")
    
    video_capture = cv2.VideoCapture(video_source)
    
    # Check if stream opened successfully
    if not video_capture.isOpened():
        print(f"[ERROR] Could not open video source {video_source}.")
        print("[ERROR] Please check your webcam connection or verify the CCTV RTSP URL in the .env file.")
        return

    print("[INFO] Video feed started successfully. Press 'q' inside the video window to quit.")

    # Flag for skipping frames to optimize CPU utilization (process every alternate frame)
    process_this_frame = True

    # Face detection/recognition storage
    face_locations = []
    face_encodings = []
    face_names = []

    try:
        while True:
            # Capture frame-by-frame
            ret, frame = video_capture.read()
            if not ret:
                print("[WARNING] Failed to grab frame. Re-trying...")
                time.sleep(0.5)
                continue

            # Check if processing this frame (alternate frames to save CPU)
            if process_this_frame:
                # Resize frame to 1/4 size for faster face recognition processing
                small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
                
                # Convert BGR (OpenCV format) to RGB (face_recognition format)
                rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
                
                # Find all the faces and face encodings in the current frame of video
                face_locations = face_recognition.face_locations(rgb_small_frame)
                face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

                face_names = []
                for face_encoding in face_encodings:
                    name = "Unknown"
                    
                    # See if the face is a match for the known face(s)
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

            # Variable to track if unknown face is present in this frame
            unknown_detected = False

            # Display the results
            for (top, right, bottom, left), name in zip(face_locations, face_names):
                # Scale back up face locations since the frame we detected in was scaled to 1/4 size
                top *= 4
                right *= 4
                bottom *= 4
                left *= 4

                # Determine color (Green for known, Red for unknown)
                if name == "Unknown":
                    color = (0, 0, 255)  # BGR Red
                    unknown_detected = True
                else:
                    color = (0, 255, 0)  # BGR Green

                # Draw a box around the face
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)

                # Draw a label with a name below the face
                cv2.rectangle(frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED)
                font = cv2.FONT_HERSHEY_DUPLEX
                cv2.putText(frame, name, (left + 6, bottom - 10), font, 0.75, (255, 255, 255), 1)

            # Alert and capture logic if an unknown person is detected
            if unknown_detected:
                current_time = time.time()
                if current_time - last_capture_time >= settings.CAPTURE_COOLDOWN_SECONDS:
                    # Capture and save the image
                    now_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    photo_name = f"captured_unknown_{now_str}.jpg"
                    photo_path = settings.CAPTURED_DIR / photo_name
                    
                    try:
                        cv2.imwrite(str(photo_path), frame)
                        print(f"[ALERT] Unknown person detected! Photo saved to {photo_path}")
                        last_capture_time = current_time
                        
                        # Send twilio alert
                        if current_time - last_alert_time >= settings.COOLDOWN_SECONDS:
                            time_display = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            notifier.send_alert(time_display, photo_name)
                            
                            # Update last alert time
                            last_alert_time = current_time
                    except Exception as e:
                        print(f"[ERROR] Failed to save photo/trigger alert: {e}")

            # Display the resulting image in a window
            cv2.imshow('Face Recognition Security Feed', frame)

            # Hit 'q' on the keyboard to stop the program
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    except KeyboardInterrupt:
        print("[INFO] Program interrupted by user.")
    finally:
        # Release handle to the webcam / CCTV stream
        print("[INFO] Releasing video source and closing windows...")
        video_capture.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
