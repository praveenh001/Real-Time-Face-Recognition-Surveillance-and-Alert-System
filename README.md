# Face Recognition Security System with Twilio Alert

A lightweight, real-time Python security system using your webcam or external CCTV RTSP streams. It detects and recognizes faces, compares them against a known folder database, and immediately captures a photo and sends a Twilio SMS notification if an unknown person is detected.

## Features
- **Dual Camera Support**: Works with standard local Webcams (via camera index) or external CCTV feeds (via RTSP URLs).
- **Intrusion Alerts**: Automatically saves a timestamped snapshot of unknown faces in the `captured/` folder.
- **Twilio SMS Notification**: Dispatches an SMS alert to your phone in a separate thread, keeping the stream lag-free.
- **Alert Cooldown**: Configurable cooldown (e.g., 5 minutes) prevents notification spam.
- **Efficient Processing**: Alternate-frame analysis and image down-scaling to reduce CPU load.

---

## Prerequisites (Windows Setup)

The Python `face_recognition` package depends on the C++ library `dlib`. Building it from source on Windows requires:

1. **Visual Studio C++ Build Tools**:
   - Download the installer from: [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
   - Run the installer and check the **Desktop development with C++** workload.
   - Install it (requires ~6-8GB of disk space).
2. **CMake**:
   - Download CMake from [cmake.org](https://cmake.org/download/) or install via package manager. Ensure it is added to your system PATH.

---

## Installation

1. Clone or open the repository folder.
2. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

---

## Configuration

1. Copy `.env.example` to `.env`:
   ```bash
   copy .env.example .env
   ```
2. Open `.env` and fill in the following configurations:
   - **Twilio details**:
     - `TWILIO_ACCOUNT_SID`: Your Twilio Account SID.
     - `TWILIO_AUTH_TOKEN`: Your Twilio Auth Token.
     - `TWILIO_FROM_NUMBER`: Your Twilio purchased phone number.
     - `TO_NUMBER`: The target phone number to receive alerts.
   - **Video source**:
     - For your primary built-in webcam, set `VIDEO_SOURCE=0`.
     - For external IP/CCTV cameras, set `VIDEO_SOURCE=rtsp://username:password@ip_address:port/stream_path`.
   - **Settings**:
     - `COOLDOWN_SECONDS`: Seconds to wait before sending another alert for unknown faces (default: `300`).
     - `TOLERANCE`: Stricteness of face match. Lower is stricter. `0.6` is default.

---

## Usage

1. **Populate Known Faces**:
   - Save photos of authorized people inside the `known_faces/` folder.
   - Name the files after the persons (e.g., `praveen.jpg`, `mom.png`). The script uses filenames to identify people.
   
2. **Run the Script**:
   ```bash
   python main.py
   ```
   
3. **Control**:
   - A window titled `Face Recognition Security Feed` will appear.
   - Press **'q'** inside the window to safely stop and close the camera feed.
