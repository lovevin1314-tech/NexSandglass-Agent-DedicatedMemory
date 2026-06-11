"""
NeuroBase Vision Bridge
=======================
Bridges py-xiaozhi's camera tool to Hermes Agent.

Can capture from:
  - Local USB camera (TNT Go ICT Camera)
  - Future: phone camera via ADB / MCP
"""
import base64
import json
import os
import tempfile
import time
from io import BytesIO

import cv2
from PIL import Image

CAPTURE_DIR = os.path.join(os.path.expanduser("~"), ".neurobase", "captures")
os.makedirs(CAPTURE_DIR, exist_ok=True)


def list_cameras(max_index=5):
    """List available cameras with their properties."""
    available = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                available.append({
                    "index": i,
                    "width": frame.shape[1],
                    "height": frame.shape[0],
                })
            cap.release()
    return available


def capture_camera(camera_index=0, save=True):
    """
    Capture a photo from the specified camera.
    
    Args:
        camera_index: Camera device index (0 = TNT Go ICT Camera)
        save: Save to file or return as bytes
        
    Returns:
        dict with image data and metadata
    """
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        return {"success": False, "error": f"Camera {camera_index} not available"}
    
    # Warm up
    time.sleep(0.2)
    for _ in range(3):
        cap.read()
    
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        return {"success": False, "error": "Failed to capture frame"}
    
    # Convert BGR to RGB
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(frame_rgb)
    
    timestamp = int(time.time())
    filename = f"capture_{timestamp}.jpg"
    filepath = os.path.join(CAPTURE_DIR, filename)
    
    if save:
        pil_img.save(filepath, "JPEG", quality=85)
    
    # Also return as base64 for direct use
    buf = BytesIO()
    pil_img.save(buf, "JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode()
    
    return {
        "success": True,
        "filepath": filepath if save else None,
        "width": frame.shape[1],
        "height": frame.shape[0],
        "base64": b64,
        "timestamp": timestamp,
    }


def analyze_with_deepseek(image_data, question="请描述你看到的内容"):
    """
    Send image to DeepSeek (via the same provider Hermes uses)
    for vision analysis.
    
    This will use my existing model provider - no extra API key needed.
    """
    # Will integrate with Hermes' vision capability
    # For now, returns the image data so the agent can process it
    return {
        "image_data": image_data,
        "question": question,
    }


if __name__ == "__main__":
    # Quick test
    cams = list_cameras()
    print(f"Available cameras: {cams}")
    
    if cams:
        result = capture_camera(cams[0]["index"])
        print(f"Capture result: {result['success']}")
        if result["success"]:
            print(f"  Saved to: {result['filepath']}")
            print(f"  Size: {result['width']}x{result['height']}")
