# import cv2

# def open_camera_stream():
#     # Replace with the IP and Port shown in your DroidCam phone app
#     # Common formats:
#     # http://192.168.0.101:4747/video
#     # http://192.168.0.101:4747/mjpegfeed
    
#     # TIP: If you are connected via USB, the IP is often 127.0.0.1 (localhost)
#     # droidcam_url = "http://10.215.39.34:4747/video" 
    
#     # print(f"Connecting to {droidcam_url}...")
#     cap = cv2.VideoCapture("http://127.0.0.1:4747/video")

#     if not cap.isOpened():
#         print("Error: Could not open video stream. Check IP/Port.")
#         return

#     print("Camera stream opened. Press 'q' to exit.")

#     while True:
#         ret, frame = cap.read()
#         if not ret:
#             break

#         cv2.imshow('DroidCam Stream', frame)
#         if cv2.waitKey(1) & 0xFF == ord('q'):
#             break

#     cap.release()
#     cv2.destroyAllWindows()

# if __name__ == "__main__":
#     open_camera_stream()

import cv2
import threading
import time

class CameraStream:
    def __init__(self, src, name="Camera"):
        self.name = name
        self.stream = cv2.VideoCapture(src)
        
        # Check if opened successfully
        if not self.stream.isOpened():
            print(f"[{self.name}] Error: Could not open stream.")
            self.stopped = True
        else:
            print(f"[{self.name}] Stream opened.")
            self.stopped = False

        # Read the first frame to initialize variables
        (self.grabbed, self.frame) = self.stream.read()

    def start(self):
        # Start the thread to read frames from the video stream
        if not self.stopped:
            threading.Thread(target=self.update, args=(), daemon=True).start()
        return self

    def update(self):
        # Keep looping indefinitely until the thread is stopped
        while True:
            # If the thread indicator variable is set, stop the thread
            if self.stopped:
                self.stream.release()
                return

            # Otherwise, read the next frame from the stream
            (grabbed, frame) = self.stream.read()
            
            # If we fail to grab a frame (e.g., disconnected), stop
            if not grabbed:
                print(f"[{self.name}] Signal lost.")
                self.stopped = True
            else:
                self.grabbed = grabbed
                self.frame = frame

    def read(self):
        # Return the most recent frame read
        return self.frame

    def stop(self):
        # Indicate that the thread should be stopped
        self.stopped = True

def run_dual_stream():
    # --- CONFIGURATION ---
    # Cam 1: USB (via ADB Forwarding)
    url_1 = "http://10.115.10.189:4747/video"
    url_2 = "http://10.215.39.34:4747/video" 
    # ---------------------

    print("Starting streams...")
    cam1 = CameraStream(url_1, "USB Cam").start()
    cam2 = CameraStream(url_2, "WiFi Cam").start()
    
    # Allow time for threads to fill the buffer
    time.sleep(1.0)

    while True:
        # Get current frames (non-blocking)
        frame1 = cam1.read()
        frame2 = cam2.read()

        # Display Cam 1
        if frame1 is not None:
            # Resize optional: keeping it small helps performance
            frame1 = cv2.resize(frame1, (640, 480))
            cv2.imshow('Feed 1: USB Base', frame1)

        # Display Cam 2
        if frame2 is not None:
            frame2 = cv2.resize(frame2, (640, 480))
            cv2.imshow('Feed 2: WiFi Rover', frame2)

        # Emergency exit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        
        # Check if both cameras died
        if cam1.stopped and cam2.stopped:
            print("All feeds lost. Exiting.")
            break

    # Cleanup
    cam1.stop()
    cam2.stop()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_dual_stream()