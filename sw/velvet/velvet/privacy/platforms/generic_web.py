"""
Generic Web, Email, and Messaging privacy and poison module.
Applies subtle perturbation, lossless audio handling, and decoy browsing.
"""

import logging
from typing import Dict, List, Any, Union

from . import PlatformPoisonModule
from ..egress_guard import ContentType, PrivacyStrength
from ..perturbation import PerturbationEngine

logger = logging.getLogger(__name__)


class GenericWebPoisonModule(PlatformPoisonModule):
    """
    Handles generic browser traffic, Email (Gmail), Signal/Telegram, and Direct File Sharing.
    Applies SUBTLE perturbations suitable for direct sharing and email attachments.
    """

    def __init__(self, platform_name: str = "generic_web"):
        super().__init__(platform_name)
        self.perturbation_engine = PerturbationEngine(PrivacyStrength.SUBTLE)

    def supported_features(self) -> Dict[str, Any]:
        return {
            "metadata_stripping": True,
            "image_perturbation": "SUBTLE",
            "audio_perturbation": "SUBTLE (WAV/FLAC)",
            "video_perturbation": "Direct file",
            "stylometric_shift": False,  # Hard Rule: User's words are never altered
            "phantom_activity": "Decoy newsletters",
            "tracker_pollution": "Decoy searches",
        }

    async def apply_egress_filter(
        self,
        content: Union[str, bytes],
        content_type: ContentType,
        is_phantom: bool = False,
        **kwargs
    ) -> Union[str, bytes]:
        """Apply generic web egress filtering."""
        if content_type == ContentType.TEXT:
            if not isinstance(content, str):
                return content
            if is_phantom:
                return await self.style_guard.apply_noise(content)
            return content

        elif content_type == ContentType.IMAGE:
            if not isinstance(content, bytes):
                return content
            stripped = await self.metadata_stripper.strip_image_metadata(content)
            return await self.perturbation_engine.perturb_image(stripped, destination=self.platform_name)

        elif content_type == ContentType.AUDIO:
            if not isinstance(content, bytes):
                return content
            stripped = await self.metadata_stripper.strip_audio_metadata(content)
            return await self.perturbation_engine.perturb_audio(stripped, destination=self.platform_name)

        elif content_type in (ContentType.VIDEO, ContentType.RAW):
            if not isinstance(content, bytes):
                return content
            return await self.perturbation_engine.perturb_video(content, destination=self.platform_name)

        return content

    def get_phantom_actions(self) -> List[Dict[str, Any]]:
        """Scheduled phantom activities (decoy browsing and newsletter signups)."""
        return [
            {"action": "search_query", "queries": ["weather forecast", "baking recipes", "wikipedia articles"]},
            {"action": "browse_articles", "domains": ["wikipedia.org", "gutenberg.org"]},
        ]
