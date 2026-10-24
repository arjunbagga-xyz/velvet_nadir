"""
Metadata stripping utilities for egress protection.
"""

import io
import logging
from PIL import Image

logger = logging.getLogger(__name__)


class MetadataStripper:
    """Strips metadata like EXIF, GPS, device IDs, and timestamps from files."""
    
    async def strip_image_metadata(self, image_bytes: bytes) -> bytes:
        """
        Strip EXIF, GPS, timestamps, and other metadata from images.
        """
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                # Retrieve pure pixel data to strip all metadata
                data = list(img.getdata())
                image_without_exif = Image.new(img.mode, img.size)
                image_without_exif.putdata(data)
                
                output = io.BytesIO()
                # Determine original format or fallback to JPEG
                format = img.format if img.format else "JPEG"
                image_without_exif.save(output, format=format)
                return output.getvalue()
        except Exception as e:
            logger.warning(f"[MetadataStripper] Failed to strip image metadata: {e}")
            return image_bytes

    async def strip_audio_metadata(self, audio_bytes: bytes) -> bytes:
        """
        Strip ID3 tags, software versions, and other metadata from audio.
        """
        # Note: Requires external libraries like mutagen for full ID3 manipulation
        logger.debug("[MetadataStripper] Audio metadata stripping is pass-through in this stub.")
        return audio_bytes
