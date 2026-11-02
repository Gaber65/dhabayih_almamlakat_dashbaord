# -*- coding: utf-8 -*-
import io
import os
import base64
import logging
from PIL import Image

_logger = logging.getLogger(__name__)

# Default logo location in static assets
LOGO_PATH = os.path.join(
    os.path.dirname(__file__),
    'static', 'src', 'img', 'app_logo.png'
)

def apply_watermark(image_bytes_or_b64, logo_path=None, opacity=0.9, scale_ratio=0.18):
    """
    Applies the Dhabayih Al-Mamlaka brand watermark onto an image.
    Accepts raw bytes or a base64 string.
    Returns: base64 string (clean, without data:image prefix).
    """
    if not image_bytes_or_b64:
        return image_bytes_or_b64

    try:
        # 1. Decode input image
        if isinstance(image_bytes_or_b64, str):
            clean_b64 = image_bytes_or_b64.strip()
            if "," in clean_b64 and "base64" in clean_b64:
                clean_b64 = clean_b64.split(",", 1)[1].strip()
            raw_bytes = base64.b64decode(clean_b64)
        else:
            raw_bytes = image_bytes_or_b64

        img = Image.open(io.BytesIO(raw_bytes))
        
        # Determine actual logo path
        actual_logo_path = logo_path or LOGO_PATH
        if not os.path.exists(actual_logo_path):
            _logger.warning("Watermark logo not found at: %s. Returning unmodified image.", actual_logo_path)
            return base64.b64encode(raw_bytes).decode('ascii') if isinstance(raw_bytes, (bytes, bytearray)) else image_bytes_or_b64

        # Convert base image to RGBA
        orig_format = img.format or 'JPEG'
        base_rgba = img.convert('RGBA')
        w, h = base_rgba.size

        # Don't watermark tiny icons / thumbnails (smaller than 120px)
        if w < 120 or h < 120:
            return base64.b64encode(raw_bytes).decode('ascii')

        # Load and resize watermark
        logo = Image.open(actual_logo_path).convert('RGBA')
        target_w = max(int(w * scale_ratio), 60)
        aspect = logo.size[1] / max(logo.size[0], 1)
        target_h = int(target_w * aspect)

        resample_mode = getattr(Image, 'Resampling', Image).LANCZOS if hasattr(Image, 'Resampling') else getattr(Image, 'LANCZOS', getattr(Image, 'ANTIALIAS', None))
        logo_resized = logo.resize((target_w, target_h), resample_mode)

        # Apply slight transparency if opacity < 1.0
        if opacity < 1.0:
            alpha = logo_resized.split()[3]
            alpha = alpha.point(lambda p: int(p * opacity))
            logo_resized.putalpha(alpha)

        # Bottom-right placement with padding
        padding = max(int(w * 0.025), 8)
        pos = (w - target_w - padding, h - target_h - padding)

        # Composite
        base_rgba.paste(logo_resized, pos, logo_resized)

        # Export as clean JPEG or PNG
        out_buf = io.BytesIO()
        if orig_format.upper() in ('PNG', 'WEBP'):
            base_rgba.save(out_buf, format=orig_format, optimize=True)
        else:
            final_rgb = base_rgba.convert('RGB')
            final_rgb.save(out_buf, format='JPEG', quality=90, optimize=True)

        return base64.b64encode(out_buf.getvalue()).decode('ascii')

    except Exception as e:
        _logger.error("Failed to apply watermark: %s", str(e), exc_info=True)
        # Fallback to returning original base64
        if isinstance(image_bytes_or_b64, str):
            clean = image_bytes_or_b64
            if "," in clean and "base64" in clean:
                clean = clean.split(",", 1)[1].strip()
            return clean
        return base64.b64encode(image_bytes_or_b64).decode('ascii')
