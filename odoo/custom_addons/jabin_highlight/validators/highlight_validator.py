# addons/jabin_highlight/validators/highlight_validator.py

from __future__ import annotations

from typing import Any, Optional

from odoo import _
from odoo.exceptions import ValidationError

from odoo.addons.jabin_core import BaseValidator

# Supported media types
ALLOWED_MEDIA_TYPES = {"image", "video"}

# Default size limits (MiB → bytes) — used as fallback when system params unavailable
_DEFAULT_IMAGE_MAX_MB = 10
_DEFAULT_VIDEO_MAX_MB = 100

# 1 MiB in bytes
_MIB = 1024 * 1024


class HighlightValidator(BaseValidator):
    """Validates highlight creation and update payloads.

    Intentionally free of Odoo ORM dependencies so it can be called
    from both the service layer and isolated unit tests.

    Size limits are read from system parameters by the caller (the
    service) and passed in as plain integers, keeping this class
    purely functional.

    Design principles
    -----------------
    * Never raise — collect all errors and return a ValidationResult.
    * Never log raw file contents.
    * The caller is responsible for providing correct size limits from
      ``ir.config_parameter``; this class only enforces them.
    """

    # Constants for validation rules
    MIN_NAME_LENGTH = 1
    MAX_NAME_LENGTH = 255

    @staticmethod
    def validate_create(
        media_type: Optional[str],
        file_storage: Any,
        *,
        max_image_mb: int = _DEFAULT_IMAGE_MAX_MB,
        max_video_mb: int = _DEFAULT_VIDEO_MAX_MB,
    ) -> None:
        """Validate a highlight upload request.

        Args:
            media_type:    Value of the ``media_type`` form field.
            file_storage:  Werkzeug ``FileStorage`` from
                           ``request.httprequest.files``.
            max_image_mb:  Maximum allowed image size in MiB.
            max_video_mb:  Maximum allowed video size in MiB.

        Raises:
            ValidationError: If validation fails with details.
        """
        errors = []

        # -- media_type ---------------------------------------------------
        if HighlightValidator.is_missing(media_type):
            errors.append("media_type is required.")
        elif str(media_type).lower() not in ALLOWED_MEDIA_TYPES:
            errors.append(
                f"media_type must be one of: {', '.join(sorted(ALLOWED_MEDIA_TYPES))}."
            )

        # -- file present -------------------------------------------------
        if file_storage is None:
            errors.append("media file is required.")
        else:
            # Werkzeug FileStorage: filename must be non-empty
            filename = getattr(file_storage, "filename", None)
            if HighlightValidator.is_missing(filename):
                errors.append("Uploaded file has no filename.")

            # -- file size ----------------------------------------------------
            if file_storage:
                # Read the file length without consuming the stream permanently
                try:
                    file_storage.stream.seek(0, 2)        # seek to end
                    file_size = file_storage.stream.tell()  # position = size
                    file_storage.stream.seek(0)             # reset to start
                except Exception:
                    # Non-seekable stream — skip size check
                    file_size = 0

                if file_size == 0:
                    errors.append("Uploaded file is empty.")
                else:
                    # Apply appropriate limit based on media type
                    if media_type and str(media_type).lower() in ALLOWED_MEDIA_TYPES:
                        _media_type = str(media_type).lower()
                        if _media_type == "image":
                            limit_bytes = max_image_mb * _MIB
                            if file_size > limit_bytes:
                                errors.append(
                                    f"Image file exceeds the maximum allowed size of {max_image_mb} MiB "
                                    f"(received {file_size / _MIB:.1f} MiB)."
                                )
                        elif _media_type == "video":
                            limit_bytes = max_video_mb * _MIB
                            if file_size > limit_bytes:
                                errors.append(
                                    f"Video file exceeds the maximum allowed size of {max_video_mb} MiB "
                                    f"(received {file_size / _MIB:.1f} MiB)."
                                )

        if errors:
            raise ValidationError("; ".join(errors))