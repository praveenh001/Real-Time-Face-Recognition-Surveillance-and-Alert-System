import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
dotenv_path = BASE_DIR / '.env'
if dotenv_path.exists():
    load_dotenv(dotenv_path)

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")
TO_NUMBER = os.getenv("TO_NUMBER", "")

# Video Source Settings
raw_video_source = os.getenv("VIDEO_SOURCE", "0")
if raw_video_source.isdigit():
    VIDEO_SOURCE = int(raw_video_source)
else:
    VIDEO_SOURCE = raw_video_source

# Face Recognition Settings
try:
    TOLERANCE = float(os.getenv("TOLERANCE", "0.6"))
except ValueError:
    TOLERANCE = 0.6

# Alert Settings
try:
    COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "300"))
except ValueError:
    COOLDOWN_SECONDS = 300

# Directories
KNOWN_FACES_DIR = BASE_DIR / "known_faces"
CAPTURED_DIR = BASE_DIR / "captured"

# Automatically create directories if they don't exist
KNOWN_FACES_DIR.mkdir(parents=True, exist_ok=True)
CAPTURED_DIR.mkdir(parents=True, exist_ok=True)
