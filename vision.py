import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import cv2
import math
import numpy as np
import time

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

        # Alert lock: hold alert for 10 seconds before allowing new detection
        self.locked_alert = None
        self.alert_lock_time = None
        self.alert_lock_duration = 10  # seconds
        self.locked_confidence = 0  # confidence score for locked alert

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

            # Detect raw alert (before lock logic) with confidence scores
            raw_alert = None
            raw_confidence = 0

            # Helper: calculate confidence (how close to threshold, capped at 100%)
            def calc_confidence(distance, threshold):
                if distance >= threshold:
                    return 0
                # Closer to 0 = higher confidence
                return min(100, int((1 - distance / threshold) * 100))

            # 1. CHOKING (Both hands at neck)
            choke_thresh = 0.6 * shoulder_width
            if dist_l_neck < choke_thresh and dist_r_neck < choke_thresh:
                 raw_alert = "CRITICAL: CHOKING DETECTED"
                 # Average confidence of both hands
                 raw_confidence = (calc_confidence(dist_l_neck, choke_thresh) +
                                   calc_confidence(dist_r_neck, choke_thresh)) // 2

            # 2. CHEST PAIN (Hand on center of chest)
            elif dist_l_chest < (0.35 * shoulder_width) or dist_r_chest < (0.45 * shoulder_width):
                 raw_alert = "URGENT: CHEST PAIN"
                 # Use the closer hand's confidence
                 conf_l = calc_confidence(dist_l_chest, 0.35 * shoulder_width)
                 conf_r = calc_confidence(dist_r_chest, 0.45 * shoulder_width)
                 raw_confidence = max(conf_l, conf_r)

            # 3. FALL (Head below hips or sudden downward movement)
            elif is_down or sudden_fall:
                 raw_alert = "CRITICAL: PATIENT DOWN"
                 if sudden_fall:
                     # Confidence based on fall velocity
                     raw_confidence = min(100, int((nose_velocity / self.fall_velocity_threshold) * 50))
                 else:
                     # Confidence based on how far below hips
                     drop_amount = nose.y - hip_mid_y
                     raw_confidence = min(100, int((drop_amount / shoulder_width) * 100) + 50)

            # 4. HEADACHE (Hand on/near head)
            elif (dist_l_head < (0.6 * shoulder_width) and l_wrist.y < l_shldr.y) or \
                 (dist_r_head < (0.6 * shoulder_width) and r_wrist.y < r_shldr.y):
                 raw_alert = "MODERATE: HEADACHE"
                 head_thresh = 0.6 * shoulder_width
                 conf_l = calc_confidence(dist_l_head, head_thresh) if l_wrist.y < l_shldr.y else 0
                 conf_r = calc_confidence(dist_r_head, head_thresh) if r_wrist.y < r_shldr.y else 0
                 raw_confidence = max(conf_l, conf_r)

            # Alert lock logic: hold alert for 10 seconds
            current_time = time.time()

            if self.locked_alert is not None:
                # Check if lock has expired
                if current_time - self.alert_lock_time >= self.alert_lock_duration:
                    # Lock expired, allow new detection
                    self.locked_alert = None
                    self.alert_lock_time = None
                    self.locked_confidence = 0
                    return annotated_frame, None
            if self.locked_alert is None and raw_alert is not None:
                # No current lock, set new one
                self.locked_alert = raw_alert
                self.alert_lock_time = current_time
                self.locked_confidence = raw_confidence

            # Use locked alert (persists for 10s) or None
            alert = self.locked_alert
            confidence = self.locked_confidence

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
                # 1. Define Prominent Styling
                font_scale = 1.5  # Increased from 0.9 for visibility
                thickness = 3
                font = cv2.FONT_HERSHEY_SIMPLEX
                color = (0, 0, 255) if "CRITICAL" in alert else (0, 165, 255)
                
                # 2. Prepare Text & Calculate Size
                alert_text = f"{alert} ({confidence}%)"
                (text_w, text_h), baseline = cv2.getTextSize(alert_text, font, font_scale, thickness)
                
                # 3. Calculate Centered Coordinates
                # h and w are height and width of annotated_frame
                h, w = annotated_frame.shape[:2] 
                
                center_x = w // 2
                center_y = h // 2
                
                text_x = center_x - (text_w // 2)
                text_y = center_y + (text_h // 2)
                
                # 4. Draw Background Box (with padding)
                padding_x, padding_y = 30, 20
                box_p1 = (text_x - padding_x, text_y - text_h - padding_y)
                box_p2 = (text_x + text_w + padding_x, text_y + padding_y + baseline)
                
                # Draw filled box
                cv2.rectangle(annotated_frame, box_p1, box_p2, color, -1)
                
                # Optional: Draw a white border around the box for contrast
                cv2.rectangle(annotated_frame, box_p1, box_p2, (255, 255, 255), 2)

                # 5. Draw Text
                cv2.putText(annotated_frame, alert_text, (text_x, text_y),
                            font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

        return annotated_frame, alert