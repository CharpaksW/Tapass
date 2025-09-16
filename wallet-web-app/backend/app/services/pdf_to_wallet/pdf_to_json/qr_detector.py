"""
QR code detection and decoding utilities.
"""

import logging
import os
from typing import List
import numpy as np

try:
    import cv2
except ImportError as e:
    raise ImportError(f"Missing required dependency: {e}. Install with: pip install opencv-python")

logger = logging.getLogger(__name__)


class QRDetector:
    """Advanced QR code detection with multiple preprocessing methods"""
    
    def __init__(self):
        self.qr_detector = cv2.QRCodeDetector()
    
    def decode_from_images(self, images: List[np.ndarray], debug_save_images: bool = False) -> List[str]:
        """Decode QR codes from images using OpenCV with enhanced detection"""
        qr_payloads = []
        
        for i, img in enumerate(images):
            page_qrs = self._process_page(img, i + 1, debug_save_images)
            qr_payloads.extend(page_qrs)
                
        logger.info(f"Total decoded: {len(qr_payloads)} QR codes")
        return qr_payloads
    
    def _process_page(self, img: np.ndarray, page_num: int, debug_save: bool) -> List[str]:
        """Process a single page for QR codes"""
        page_qr_count = 0
        page_qrs = []
        
        try:
            # Convert to grayscale for better QR detection
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Try multiple preprocessing approaches for better detection
            preprocessed_images = self._get_preprocessed_images(gray)
            
            found_qrs = set()  # Use set to avoid duplicates
            
            for j, processed_img in enumerate(preprocessed_images):
                try:
                    # Try multi-QR detection first
                    retval, decoded_info, points, _ = self.qr_detector.detectAndDecodeMulti(processed_img)
                    
                    if retval and decoded_info:
                        for decoded in decoded_info:
                            if decoded and decoded.strip():
                                qr_text = decoded.strip()
                                if qr_text not in found_qrs:
                                    found_qrs.add(qr_text)
                                    page_qrs.append(qr_text)
                                    page_qr_count += 1
                                    logger.debug(f"Found QR on page {page_num} (multi-method {j+1}): {qr_text[:50]}...")
                    
                    # Also try single QR detection as fallback
                    try:
                        decoded_single, points_single, _ = self.qr_detector.detectAndDecode(processed_img)
                        if decoded_single and decoded_single.strip():
                            qr_text = decoded_single.strip()
                            if qr_text not in found_qrs:
                                found_qrs.add(qr_text)
                                page_qrs.append(qr_text)
                                page_qr_count += 1
                                logger.debug(f"Found QR on page {page_num} (single-method {j+1}): {qr_text[:50]}...")
                    except Exception as single_e:
                        logger.debug(f"Single QR detection method {j+1} failed on page {page_num}: {single_e}")
                                        
                except Exception as method_e:
                    logger.debug(f"QR detection method {j+1} failed on page {page_num}: {method_e}")
                    
            if page_qr_count > 0:
                logger.info(f"Page {page_num}: Found {page_qr_count} QR code(s)")
            else:
                logger.warning(f"Page {page_num}: No QR codes found despite trying {len(preprocessed_images)} different methods")
                
            # Save debug images if requested
            #if debug_save:
            #    self._save_debug_images(img, gray, preprocessed_images, page_num)
                        
        except Exception as e:
            logger.warning(f"QR detection failed on page {page_num}: {e}")
            
        return page_qrs
    
    def _get_preprocessed_images(self, gray: np.ndarray) -> List[np.ndarray]:
        """Generate multiple preprocessed versions of the image for better QR detection"""
        preprocessed_images = [
            gray,  # Original grayscale
            cv2.GaussianBlur(gray, (3, 3), 0),  # Slight blur to reduce noise
            cv2.GaussianBlur(gray, (5, 5), 0),  # More blur
            cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2),  # Adaptive threshold
            cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 2),  # Different adaptive threshold
            cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],  # Otsu thresholding
            cv2.equalizeHist(gray),  # Histogram equalization for better contrast
            cv2.morphologyEx(gray, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))),  # Morphological closing
            cv2.bilateralFilter(gray, 9, 75, 75)  # Bilateral filter to reduce noise while keeping edges
        ]
        
        # Also try different scales
        height, width = gray.shape
        for scale in [0.5, 1.5, 2.0]:
            if scale != 1.0:
                new_width = int(width * scale)
                new_height = int(height * scale)
                scaled = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
                preprocessed_images.append(scaled)
                
        return preprocessed_images
    
    def _save_debug_images(self, img: np.ndarray, gray: np.ndarray, 
                          preprocessed_images: List[np.ndarray], page_num: int) -> None:
        """Save debug images for visual inspection"""
        try:
            os.makedirs("debug_qr", exist_ok=True)
            cv2.imwrite(f"debug_qr/page_{page_num}_original.png", img)
            cv2.imwrite(f"debug_qr/page_{page_num}_gray.png", gray)
            for j, processed in enumerate(preprocessed_images[:5]):  # Save first 5 methods only
                cv2.imwrite(f"debug_qr/page_{page_num}_method_{j+1}.png", processed)
        except Exception as e:
            logger.warning(f"Failed to save debug images for page {page_num}: {e}")
