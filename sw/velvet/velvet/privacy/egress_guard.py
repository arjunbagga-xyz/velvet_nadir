"""
System-level egress protection framework.
"""

import asyncio
import logging
from enum import Enum
from typing import Any, Dict, Optional, Tuple, Union

from velvet.mirage import MirageProxy, MirageMap
from .metadata_strip import MetadataStripper
from .perturbation import PerturbationEngine
from .style_guard import StyleGuard

logger = logging.getLogger(__name__)


class PrivacyStrength(Enum):
    """Global perturbation strength setting."""
    SUBTLE = "subtle"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


class ContentType(Enum):
    """Types of content that can pass through EgressGuard."""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    RAW = "raw"


class EgressGuard:
    """
    System-level egress protection. Everything leaving the mesh passes through here.
    Intercepts at Gateway level.
    
    Pipeline:
    1. MetadataStripper (always) — EXIF, GPS, device IDs, timestamps
    2. PerturbationEngine (media) — adversarial perturbation for images
    3. PrivacyGuard (PII check) — delegates to existing MirageProxy
    4. StyleGuard (text, auto-generated only) — stylometric noise
    """
    
    def __init__(self, strength: PrivacyStrength = PrivacyStrength.BALANCED):
        """Initialize the EgressGuard with a specific privacy strength."""
        self.strength = strength
        self.metadata_stripper = MetadataStripper()
        self.perturbation_engine = PerturbationEngine(self.strength)
        self.mirage_proxy = MirageProxy()
        self.style_guard = StyleGuard(self.strength)
    
    async def process(
        self, 
        content: Union[str, bytes], 
        content_type: ContentType, 
        auto_generated: bool = False, 
        destination: str = "default",
        smap: Optional[MirageMap] = None
    ) -> Union[str, bytes, Tuple[str, Optional[MirageMap]]]:
        """
        Process content leaving the mesh based on its type.
        
        Args:
            content: The payload to process.
            content_type: The type of the content.
            auto_generated: Critical flag to identify system-generated content.
            destination: The target destination for adjusting perturbation.
            smap: Optional MirageMap for PII text scrambling.
            
        Returns:
            Processed content (and MirageMap for text).
        """
        if content_type == ContentType.TEXT:
            if not isinstance(content, str):
                raise ValueError("Content must be string for TEXT type")
            return await self._process_text(content, auto_generated, smap)
            
        elif content_type == ContentType.IMAGE:
            if not isinstance(content, bytes):
                raise ValueError("Content must be bytes for IMAGE type")
            return await self._process_image(content, destination)
            
        elif content_type == ContentType.AUDIO:
            if not isinstance(content, bytes):
                raise ValueError("Content must be bytes for AUDIO type")
            return await self._process_audio(content, destination)
            
        elif content_type in [ContentType.VIDEO, ContentType.RAW]:
            if not isinstance(content, bytes):
                raise ValueError("Content must be bytes for VIDEO/RAW type")
            return await self._process_raw(content, destination)
            
        return content

    async def _process_text(self, text: str, auto_generated: bool, smap: Optional[MirageMap]) -> Tuple[str, Optional[MirageMap]]:
        """
        Process outbound text content.
        Only applies stylometric noise to auto_generated text. User text is never modified for style.
        """
        # 1. PII check via MirageProxy (applies to all text)
        scrambled_text, updated_smap = self.mirage_proxy.scramble(text, smap)
        
        # 2. StyleGuard (only if auto-generated)
        if auto_generated:
            scrambled_text = await self.style_guard.apply_noise(scrambled_text)
            
        return scrambled_text, updated_smap
        
    async def _process_image(self, image_data: bytes, destination: str) -> bytes:
        """Process outbound image content."""
        # 1. Strip Metadata
        stripped_image = await self.metadata_stripper.strip_image_metadata(image_data)
        # 2. Apply Adversarial Perturbation
        perturbed_image = await self.perturbation_engine.perturb_image(stripped_image, destination)
        return perturbed_image
        
    async def _process_audio(self, audio_data: bytes, destination: str = "default") -> bytes:
        """Process outbound audio content."""
        stripped = await self.metadata_stripper.strip_audio_metadata(audio_data)
        return await self.perturbation_engine.perturb_audio(stripped, destination)

    async def _process_raw(self, raw_data: bytes, destination: str = "default") -> bytes:
        """Process outbound raw/video content."""
        return await self.perturbation_engine.perturb_video(raw_data, destination)
