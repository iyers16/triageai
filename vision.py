import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import cv2
import math
import numpy as np

class VisionTriage:
    def __init__(self):
        # 1. SETUP MODEL
        base_options = python.BaseOptions(model_asset_path='pose_landmarker_lite.task')
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            output_segmentation_masks=False,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.detector = vision.PoseLandmarker.create_from_options(options)

        # Fall detection: track previous nose position for sudden movement
        self.prev_nose_y = None
        self.fall_velocity_threshold = 0.05  # Sudden downward movement threshold

        # Define connections for drawing the skeleton (Bone Map)
        self.CONNECTIONS = [
            (11, 12), (11, 13), (13, 15), # Left Arm
            (12, 14), (14, 16),           # Right Arm
            (11, 23), (12, 24), (23, 24)  # Torso
        ]

    def _get_distance(self, p1, p2):
        return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

    def analyze_frame(self, frame):
        # Flip frame for "mirror" effect (more natural interaction)
        frame = cv2.flip(frame, 1)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
        
        detection_result = self.detector.detect(mp_image)
        alert = None
        annotated_frame = frame.copy()
        
        if detection_result.pose_landmarks:
            landmarks = detection_result.pose_landmarks[0]
            h, w, _ = frame.shape

            # Extract Key Landmarks
            # 11-12: Shoulders, 13-14: Elbows, 15-16: Wrists, 23-24: Hips
            l_shldr, r_shldr = landmarks[11], landmarks[12]
            l_wrist, r_wrist = landmarks[15], landmarks[16]
            nose = landmarks[0]
            l_hip, r_hip = landmarks[23], landmarks[24]

            # --- DYNAMIC SCALE CALCULATION ---
            # We use shoulder width as our "ruler". 
            # If the person is far away, this number is small. If close, it's big.
            shoulder_width = self._get_distance(l_shldr, r_shldr)
            
            # Avoid division by zero if detection is glitchy
            if shoulder_width < 0.01: shoulder_width = 0.01

            # Calculate Neck Position (Midpoint of shoulders)
            neck_x = (l_shldr.x + r_shldr.x) / 2
            neck_y = (l_shldr.y + r_shldr.y) / 2
            
            # --- MEDICAL LOGIC (Ratio Based) ---
            
            # Calculate Chest Center (midpoint between shoulders, slightly below)
            chest_x = (l_shldr.x + r_shldr.x) / 2
            chest_y = (l_shldr.y + r_shldr.y) / 2 + (0.3 * shoulder_width)

            # Calculate distances for detection
            dist_l_neck = math.sqrt((l_wrist.x - neck_x)**2 + (l_wrist.y - neck_y)**2)
            dist_r_neck = math.sqrt((r_wrist.x - neck_x)**2 + (r_wrist.y - neck_y)**2)
            dist_l_chest = math.sqrt((l_wrist.x - chest_x)**2 + (l_wrist.y - chest_y)**2)
            dist_r_chest = math.sqrt((r_wrist.x - chest_x)**2 + (r_wrist.y - chest_y)**2)
            dist_l_head = self._get_distance(l_wrist, nose)
            dist_r_head = self._get_distance(r_wrist, nose)

            # Fall detection calculations
            hip_mid_y = (l_hip.y + r_hip.y) / 2

            # Detect sudden downward movement
            sudden_fall = False
            if self.prev_nose_y is not None:
                nose_velocity = nose.y - self.prev_nose_y  # Positive = moving down
                if nose_velocity > self.fall_velocity_threshold:
                    sudden_fall = True
            self.prev_nose_y = nose.y

            is_down = nose.y > hip_mid_y  # Head below hips

            # 1. CHOKING (Both hands at neck)
            if dist_l_neck < (0.6 * shoulder_width) and dist_r_neck < (0.6 * shoulder_width):
                 alert = "CRITICAL: CHOKING DETECTED"

            # 2. CHEST PAIN (Hand on center of chest)
            elif dist_l_chest < (0.35 * shoulder_width) or dist_r_chest < (0.45 * shoulder_width):
                 alert = "URGENT: CHEST PAIN"

            # 3. FALL (Head below hips or sudden downward movement)
            elif is_down or sudden_fall:
                 alert = "CRITICAL: PATIENT DOWN"

            # 4. HEADACHE (Hand on/near head)
            elif (dist_l_head < (0.6 * shoulder_width) and l_wrist.y < l_shldr.y) or \
                 (dist_r_head < (0.6 * shoulder_width) and r_wrist.y < r_shldr.y):
                 alert = "MODERATE: HEADACHE"

            # --- DRAWING THE SKELETON ---
            # 1. Draw Bones (Lines)
            for start_idx, end_idx in self.CONNECTIONS:
                start_point = landmarks[start_idx]
                end_point = landmarks[end_idx]
                
                # Convert normalized (0-1) to pixel coordinates
                p1 = (int(start_point.x * w), int(start_point.y * h))
                p2 = (int(end_point.x * w), int(end_point.y * h))
                
                cv2.line(annotated_frame, p1, p2, (255, 255, 255), 2) # White bones

            # 2. Draw Joints (Circles)
            for lm in [l_shldr, r_shldr, l_wrist, r_wrist, nose, l_hip]:
                cx, cy = int(lm.x * w), int(lm.y * h)
                cv2.circle(annotated_frame, (cx, cy), 6, (0, 255, 0), -1) # Green joints

            # 3. Draw Alert Banner if needed
            if alert:
                color = (0, 0, 255) if "CRITICAL" in alert else (0, 165, 255)
                cv2.rectangle(annotated_frame, (0, 0), (w, 60), color, -1)
                cv2.putText(annotated_frame, alert, (20, 40), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)

        return annotated_frame, alert