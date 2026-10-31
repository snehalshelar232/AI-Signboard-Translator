import cv2
import numpy as np
from typing import Tuple, Dict, Any

class ImagePreprocessor:
    """
    Evaluates signboard image clarity and applies adaptive preprocessing
    to maximize character stroke clarity without destroying Indic vowel marks or ligatures.
    """

    @staticmethod
    def assess_clarity(image_bytes: bytes) -> Dict[str, Any]:
        """
        Calculates blur variance, brightness, and contrast metrics.
        Returns diagnostic information to flag unreadable or blurry signboards.
        """
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {
                "is_valid": False,
                "blur_score": 0.0,
                "is_blurry": True,
                "brightness": 0.0,
                "is_dark": True,
                "clarity_score": 0.0,
                "warning": "Could not decode uploaded image."
            }

        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Laplacian variance (sharpness / blur detection)
        # Higher score = sharper image. Values below 50 generally mean motion blur or out of focus.
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        is_blurry = laplacian_var < 50.0

        # Brightness & Contrast
        brightness = float(np.mean(gray))
        contrast = float(np.std(gray))
        is_dark = brightness < 50.0
        is_low_contrast = contrast < 25.0

        # Normalized clarity score between 0.0 and 1.0
        # Combines sharpness and contrast
        sharpness_component = min(laplacian_var / 300.0, 1.0)
        contrast_component = min(contrast / 60.0, 1.0)
        clarity_score = round(0.6 * sharpness_component + 0.4 * contrast_component, 2)

        warnings = []
        if is_blurry:
            warnings.append("Image appears blurry or out of focus.")
        if is_dark:
            warnings.append("Image is very dark. Outdoor lighting or flash recommended.")
        if is_low_contrast:
            warnings.append("Low contrast between text and signboard background.")

        return {
            "is_valid": True,
            "blur_score": round(laplacian_var, 1),
            "is_blurry": is_blurry,
            "brightness": round(brightness, 1),
            "is_dark": is_dark,
            "contrast": round(contrast, 1),
            "is_low_contrast": is_low_contrast,
            "clarity_score": clarity_score,
            "warning": " | ".join(warnings) if warnings else None,
            "width": img.shape[1],
            "height": img.shape[0]
        }

    @staticmethod
    def preprocess_if_needed(image_bytes: bytes) -> Tuple[bytes, bool]:
        """
        Enhances image to maximize character stroke clarity without destroying Indic vowel marks or ligatures.
        Handles:
        - Upscaling small/low-res signboard crops so Indic conjuncts and matras are distinguishable.
        - Downsampling ultra-high-res phone camera uploads to optimal OCR dimensions.
        - Auto-trimming solid letterbox borders.
        - Adaptive CLAHE contrast enhancement for low-light or backlit roadside signboards.
        - Subtle unsharp masking for crisper character boundary definition.
        """
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return image_bytes, False

        applied_preprocessing = False
        processed = img.copy()
        h, w = processed.shape[:2]

        # Step 1: Smart border / letterbox trimming (if image has thick solid black or white borders)
        try:
            gray_for_crop = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
            # Find bounding box of non-extreme pixels (ignore border padding)
            _, thresh_dark = cv2.threshold(gray_for_crop, 15, 255, cv2.THRESH_BINARY)
            _, thresh_light = cv2.threshold(gray_for_crop, 245, 255, cv2.THRESH_BINARY_INV)
            mask = cv2.bitwise_and(thresh_dark, thresh_light)
            coords = cv2.findNonZero(mask)
            if coords is not None:
                x_b, y_b, w_b, h_b = cv2.boundingRect(coords)
                # Only crop if at least 10% of image was border padding and remaining box is substantial
                if (w_b * h_b) < 0.90 * (w * h) and w_b > 120 and h_b > 60:
                    # Keep small margin
                    pad_x = int(0.02 * w)
                    pad_y = int(0.02 * h)
                    x1 = max(0, x_b - pad_x)
                    y1 = max(0, y_b - pad_y)
                    x2 = min(w, x_b + w_b + pad_x)
                    y2 = min(h, y_b + h_b + pad_y)
                    if (x2 - x1) > 100 and (y2 - y1) > 50:
                        processed = processed[y1:y2, x1:x2]
                        applied_preprocessing = True
                        h, w = processed.shape[:2]
        except Exception:
            pass

        # Step 2: Intelligent Resizing
        # Upscale small images so complex Marathi (e.g. ळ, द्रुतगती) & Gujarati characters have enough pixel density
        if w < 720 or h < 360:
            scale_w = 720 / float(w)
            scale_h = 360 / float(h)
            scale = min(max(scale_w, scale_h), 2.5)
            new_w = int(w * scale)
            new_h = int(h * scale)
            processed = cv2.resize(processed, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            applied_preprocessing = True
            h, w = processed.shape[:2]
        elif max(h, w) > 2048:
            # Downsample massive images (e.g. 48MP phone cameras) while preserving aspect ratio
            scaling = 2048.0 / float(max(h, w))
            new_w = int(w * scaling)
            new_h = int(h * scaling)
            processed = cv2.resize(processed, (new_w, new_h), interpolation=cv2.INTER_AREA)
            applied_preprocessing = True
            h, w = processed.shape[:2]

        # Step 3: Contrast & Illumination Enhancement via CLAHE on L channel
        gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
        contrast = float(np.std(gray))
        brightness = float(np.mean(gray))

        if contrast < 45.0 or brightness < 70.0 or brightness > 220.0:
            lab = cv2.cvtColor(processed, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.4, tileGridSize=(8, 8))
            cl = clahe.apply(l)
            limg = cv2.merge((cl, a, b))
            processed = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
            applied_preprocessing = True

        # Step 4: Subtle unsharp mask to crisply define text boundaries for Indic characters
        if contrast < 55.0:
            gaussian = cv2.GaussianBlur(processed, (0, 0), 2.0)
            unsharp = cv2.addWeighted(processed, 1.25, gaussian, -0.25, 0)
            processed = unsharp
            applied_preprocessing = True

        if applied_preprocessing:
            success, encoded_img = cv2.imencode(".jpg", processed, [cv2.IMWRITE_JPEG_QUALITY, 95])
            if success:
                return encoded_img.tobytes(), True

        return image_bytes, False
