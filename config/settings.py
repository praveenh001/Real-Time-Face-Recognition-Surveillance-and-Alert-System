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

def save_settings(updates):
    """
    Saves new settings back to the .env file and updates current in-memory configurations.
    """
    global TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, TO_NUMBER, VIDEO_SOURCE, TOLERANCE, COOLDOWN_SECONDS
    
    # Read existing values
    env_content = {}
    if dotenv_path.exists():
        with open(dotenv_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    env_content[k.strip()] = v.strip()

    # Update dictionary and in-memory variables
    for k, v in updates.items():
        env_content[k] = str(v)
        if k == "TWILIO_ACCOUNT_SID":
            TWILIO_ACCOUNT_SID = str(v)
        elif k == "TWILIO_AUTH_TOKEN":
            TWILIO_AUTH_TOKEN = str(v)
        elif k == "TWILIO_FROM_NUMBER":
            TWILIO_FROM_NUMBER = str(v)
        elif k == "TO_NUMBER":
            TO_NUMBER = str(v)
        elif k == "VIDEO_SOURCE":
            raw = str(v)
            VIDEO_SOURCE = int(raw) if raw.isdigit() else raw
        elif k == "TOLERANCE":
            TOLERANCE = float(v)
        elif k == "COOLDOWN_SECONDS":
            COOLDOWN_SECONDS = int(v)

    # Write back to .env
    lines = [
        "# Twilio API credentials",
        f"TWILIO_ACCOUNT_SID={env_content.get('TWILIO_ACCOUNT_SID', '')}",
        f"TWILIO_AUTH_TOKEN={env_content.get('TWILIO_AUTH_TOKEN', '')}",
        f"TWILIO_FROM_NUMBER={env_content.get('TWILIO_FROM_NUMBER', '')}",
        f"TO_NUMBER={env_content.get('TO_NUMBER', '')}",
        "",
        "# Video source (0 for webcam, or RTSP URL)",
        f"VIDEO_SOURCE={env_content.get('VIDEO_SOURCE', '0')}",
        "",
        "# Alert configuration",
        f"COOLDOWN_SECONDS={env_content.get('COOLDOWN_SECONDS', '300')}",
        f"TOLERANCE={env_content.get('TOLERANCE', '0.6')}"
    ]

    with open(dotenv_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')

