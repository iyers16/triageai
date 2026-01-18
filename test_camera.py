import cv2

def open_camera_stream():
    # Replace with the IP and Port shown in your DroidCam phone app
    # Common formats:
    # http://192.168.0.101:4747/video
    # http://192.168.0.101:4747/mjpegfeed
    
    # TIP: If you are connected via USB, the IP is often 127.0.0.1 (localhost)
    # droidcam_url = "http://10.215.39.34:4747/video" 
    
    # print(f"Connecting to {droidcam_url}...")
    cap = cv2.VideoCapture("http://10.102.199.32:4747/video")

    if not cap.isOpened():
        print("Error: Could not open video stream. Check IP/Port.")
        return

    print("Camera stream opened. Press 'q' to exit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        cv2.imshow('DroidCam Stream', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    open_camera_stream()