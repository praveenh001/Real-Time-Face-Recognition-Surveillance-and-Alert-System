// UI DOM Elements
const systemStatus = document.getElementById("system-status-indicator");
const liveTimeEl = document.getElementById("live-time");
const cameraStatusBadge = document.getElementById("camera-status-badge");
const videoStreamEl = document.getElementById("video-stream");
const streamFallbackEl = document.getElementById("stream-fallback");

const uploadForm = document.getElementById("upload-form");
const fileInput = document.getElementById("person-photo");
const nameInput = document.getElementById("person-name");
const dropzone = document.getElementById("dropzone");
const uploadFeedback = document.getElementById("upload-feedback");

const settingsForm = document.getElementById("settings-form");
const inputVideoSource = document.getElementById("set-video-source");
const inputTolerance = document.getElementById("set-tolerance");
const inputCooldown = document.getElementById("set-cooldown");
const inputTwilioSid = document.getElementById("set-twilio-sid");
const inputTwilioToken = document.getElementById("set-twilio-token");
const inputTwilioFrom = document.getElementById("set-twilio-from");
const inputToNumber = document.getElementById("set-to-number");
const settingsFeedback = document.getElementById("settings-feedback");

const intruderTimeline = document.getElementById("intruder-timeline");
const refreshLogBtn = document.getElementById("btn-refresh-log");

const imageModal = document.getElementById("image-modal");
const modalImg = document.getElementById("modal-img");
const modalCaption = document.getElementById("modal-caption");

// Global state variables
let lastDetectionsCount = 0;

// Initialize Dashboard
document.addEventListener("DOMContentLoaded", () => {
    // 1. Start live time update
    updateTime();
    setInterval(updateTime, 1000);

    // 2. Fetch current configurations
    fetchSettings();

    // 3. Load intruder detections timeline
    fetchIntruderLogs();
    // Poll logs every 5 seconds to look for fresh intrusions
    setInterval(fetchIntruderLogs, 5000);

    // 4. Set dropzone events
    fileInput.addEventListener("change", updateDropzoneText);
    
    // 5. Setup Form Submit Listeners
    uploadForm.addEventListener("submit", handleEnrollmentSubmit);
    settingsForm.addEventListener("submit", handleSettingsSubmit);
    refreshLogBtn.addEventListener("click", fetchIntruderLogs);
});

// Update the navbar clock
function updateTime() {
    const now = new Date();
    liveTimeEl.textContent = now.toLocaleDateString() + " " + now.toLocaleTimeString();
}

// Fallback if the MJPEG feed fails
function handleStreamError() {
    videoStreamEl.classList.add("hidden");
    streamFallbackEl.classList.remove("hidden");
    cameraStatusBadge.textContent = "Offline";
    cameraStatusBadge.style.backgroundColor = "rgba(244, 63, 94, 0.15)";
    cameraStatusBadge.style.color = "#f43f5e";
    cameraStatusBadge.style.borderColor = "rgba(244, 63, 94, 0.3)";
    
    systemStatus.classList.remove("alert-safe-color");
    systemStatus.classList.add("alert-danger-color");
}

// Update file drag text
function updateDropzoneText() {
    if (fileInput.files.length > 0) {
        document.querySelector(".dropzone-text").textContent = "Selected: " + fileInput.files[0].name;
    } else {
        document.querySelector(".dropzone-text").textContent = "Click to choose or Drag file here";
    }
}

// Fetch Settings from server APIs
async function fetchSettings() {
    try {
        const response = await fetch("/api/settings");
        if (response.ok) {
            const data = await response.json();
            inputVideoSource.value = data.VIDEO_SOURCE;
            inputTolerance.value = data.TOLERANCE;
            inputCooldown.value = data.COOLDOWN_SECONDS;
            inputTwilioSid.value = data.TWILIO_ACCOUNT_SID;
            inputTwilioToken.value = data.TWILIO_AUTH_TOKEN;
            inputTwilioFrom.value = data.TWILIO_FROM_NUMBER;
            inputToNumber.value = data.TO_NUMBER;
            
            // Set dynamic camera badge text
            const src = data.VIDEO_SOURCE;
            cameraStatusBadge.textContent = isNaN(src) ? "Network Stream" : "Webcam Feed (Index " + src + ")";
        }
    } catch (err) {
        console.error("Failed to load settings:", err);
    }
}

// Submit updated configuration
async function handleSettingsSubmit(e) {
    e.preventDefault();
    showFeedback(settingsFeedback, "Saving configuration...", "success");

    const payload = {
        VIDEO_SOURCE: inputVideoSource.value,
        TOLERANCE: parseFloat(inputTolerance.value),
        COOLDOWN_SECONDS: parseInt(inputCooldown.value),
        TWILIO_ACCOUNT_SID: inputTwilioSid.value,
        TWILIO_AUTH_TOKEN: inputTwilioToken.value,
        TWILIO_FROM_NUMBER: inputTwilioFrom.value,
        TO_NUMBER: inputToNumber.value
    };

    try {
        const response = await fetch("/api/settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            showFeedback(settingsFeedback, "Configurations applied and saved successfully!", "success");
            // If the camera source changed, reload the video image source
            setTimeout(() => {
                videoStreamEl.src = "/video_feed?t=" + new Date().getTime();
                videoStreamEl.classList.remove("hidden");
                streamFallbackEl.classList.add("hidden");
                fetchSettings();
            }, 1000);
        } else {
            const errData = await response.json();
            showFeedback(settingsFeedback, "Failed: " + (errData.error || "Unknown server error"), "error");
        }
    } catch (err) {
        showFeedback(settingsFeedback, "Failed to connect to configurations server: " + err, "error");
    }
}

// Submit face enrollment
async function handleEnrollmentSubmit(e) {
    e.preventDefault();
    showFeedback(uploadFeedback, "Processing and encoding face image...", "success");

    const btn = document.getElementById("btn-upload");
    btn.disabled = true;

    const formData = new FormData();
    formData.append("name", nameInput.value);
    formData.append("photo", fileInput.files[0]);

    try {
        const response = await fetch("/api/upload", {
            method: "POST",
            body: formData
        });

        const data = await response.json();
        if (response.ok) {
            showFeedback(uploadFeedback, `Successfully registered ${nameInput.value}! Face encoding loaded.`, "success");
            uploadForm.reset();
            updateDropzoneText();
        } else {
            showFeedback(uploadFeedback, "Registration failed: " + (data.error || "Verify image contains a clear face"), "error");
        }
    } catch (err) {
        showFeedback(uploadFeedback, "Failed to upload file: " + err, "error");
    } finally {
        btn.disabled = false;
    }
}

// Fetch intrusion history
async function fetchIntruderLogs() {
    try {
        const response = await fetch("/api/captured");
        if (response.ok) {
            const data = await response.json();
            
            // Check if we have new intrusions to trigger a red navbar state
            if (data.length > lastDetectionsCount) {
                if (lastDetectionsCount > 0) {
                    // Flash red status indicator
                    triggerIntruderAlertFlash();
                }
                lastDetectionsCount = data.length;
            }

            renderLogs(data);
        }
    } catch (err) {
        console.error("Failed to load logs:", err);
    }
}

// Update log cards inside timeline
function renderLogs(logs) {
    if (logs.length === 0) {
        intruderTimeline.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" class="empty-icon"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>
                <p>No intrusion events captured yet.</p>
            </div>`;
        return;
    }

    // Sort by timestamp descending
    logs.sort((a, b) => b.timestamp.localeCompare(a.timestamp));

    let html = "";
    logs.forEach(log => {
        const cleanTime = log.timestamp.replace(/_/g, ' ').substring(0, 19);
        html += `
            <div class="log-item" onclick="openModal('${log.url}', 'Unknown Intruder - ${cleanTime}')">
                <img class="log-thumbnail" src="${log.url}" alt="Thumbnail">
                <div class="log-details">
                    <span class="log-title">🚨 Intrusion Detected</span>
                    <span class="log-time">${cleanTime}</span>
                </div>
            </div>`;
    });
    intruderTimeline.innerHTML = html;
}

// Status indicator animation
function triggerIntruderAlertFlash() {
    systemStatus.classList.remove("alert-safe-color");
    systemStatus.classList.add("alert-danger-color");
    
    // Revert back to green after 10 seconds
    setTimeout(() => {
        systemStatus.classList.remove("alert-danger-color");
        systemStatus.classList.add("alert-safe-color");
    }, 10000);
}

// Help utility for rendering form alerts
function showFeedback(el, msg, type) {
    el.textContent = msg;
    el.className = "feedback-msg";
    el.classList.add(type === "error" ? "feedback-error" : "feedback-success");
    el.classList.remove("hidden");
    
    if (type === "success") {
        setTimeout(() => {
            el.classList.add("hidden");
        }, 5000);
    }
}

// Modal view utilities
function openModal(imgUrl, captionText) {
    imageModal.classList.remove("hidden");
    modalImg.src = imgUrl;
    modalCaption.textContent = captionText;
}

function closeModal() {
    imageModal.classList.add("hidden");
}
