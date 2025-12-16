from PIL import Image, ImageFilter
import cv2
import numpy as np
import io
from .logging_config import get_logger, log_error

logger = get_logger(__name__)

class LicensePlateBlurrer:
    def __init__(self):
        # Load pre-trained cascade for license plate detection
        # You can use OpenCV's Haar Cascade or YOLO model
        try:
            self.plate_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_russian_plate_number.xml'
            )
        except:
            logger.warning("License plate cascade not loaded, using fallback detection")
            self.plate_cascade = None
    
    def blur_license_plate(self, image_bytes: bytes) -> bytes:
        """Detect and blur license plates in image"""
        try:
            # Convert bytes to numpy array
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                return image_bytes
            
            # Convert to grayscale for detection
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Detect license plates
            plates = self._detect_plates(gray)
            
            # Blur detected regions
            for (x, y, w, h) in plates:
                # Add padding around detected plate
                padding = 10
                x1 = max(0, x - padding)
                y1 = max(0, y - padding)
                x2 = min(img.shape[1], x + w + padding)
                y2 = min(img.shape[0], y + h + padding)
                
                # Apply strong Gaussian blur
                roi = img[y1:y2, x1:x2]
                blurred_roi = cv2.GaussianBlur(roi, (51, 51), 30)
                img[y1:y2, x1:x2] = blurred_roi
            
            # Convert back to bytes
            _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            return buffer.tobytes()
            
        except Exception as e:
            log_error(logger, e, {}, "license_plate_blur_error")
            return image_bytes  # Return original if processing fails
    
    def _detect_plates(self, gray_image):
        """Detect license plate regions"""
        plates = []
        
        # Method 1: Haar Cascade
        if self.plate_cascade:
            detected = self.plate_cascade.detectMultiScale(
                gray_image, 
                scaleFactor=1.1, 
                minNeighbors=5,
                minSize=(50, 15)
            )
            plates.extend(detected)
        
        # Method 2: Contour-based detection (fallback)
        if len(plates) == 0:
            plates = self._detect_by_contours(gray_image)
        
        return plates
    
    def _detect_by_contours(self, gray_image):
        """Fallback: Detect rectangular regions that might be plates"""
        plates = []
        
        # Apply edge detection
        edges = cv2.Canny(gray_image, 100, 200)
        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / float(h)
            
            # License plates typically have aspect ratio between 2:1 and 5:1
            if 2.0 <= aspect_ratio <= 5.0 and w > 50 and h > 15:
                plates.append((x, y, w, h))
        
        return plates

# Global instance
plate_blurrer = LicensePlateBlurrer()