import cv2
import os

# Bắt buộc cho EZVIZ
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

rtsp_url = "rtsp://admin:XGIMBN@192.168.100.23:554/ch1/main"

cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)

if not cap.isOpened():
    print("❌ Cannot connect to camera")
    exit()

print("✅ Camera connected")

while True:
    ret, frame = cap.read()
    
    if not ret:
        print("❌ Cannot read frame")
        break
    
    cv2.imshow("ParkSmart Gate", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()