"""
Twitter / X privacy and poison module.
Applies balanced image perturbation, metadata stripping, and phantom activity.
"""

import logging
from typing import Dict, List, Any, Union

from . import PlatformPoisonModule
from ..egress_guard import ContentType, PrivacyStrength
from ..perturbation import PerturbationEngine

logger = logging.getLogger(__name__)


class TwitterPoisonModule(PlatformPoisonModule):
    """
    Twitter/X-specific defense module.
    Applies BALANCED perturbation to images and manages phantom decoy trends and timeline browsing.
    """

    def __init__(self):
        super().__init__("twitter")
        self.perturbation_engine = PerturbationEngine(PrivacyStrength.BALANCED)

    def supported_features(self) -> Dict[str, Any]:
        return {
            "metadata_stripping": True,
            "image_perturbation": "BALANCED",
            "audio_perturbation": False,  # Twitter has no native standalone audio post
            "video_perturbation": "Offline only",
            "stylometric_shift": False,  # Hard Rule: User's words are never altered
            "phantom_activity": "Decoy trends",
            "tracker_pollution": "Timeline scroll",
        }

    async def apply_egress_filter(
        self,
        content: Union[str, bytes],
        content_type: ContentType,
        is_phantom: bool = False,
        **kwargs
    ) -> Union[str, bytes]:
        """Apply Twitter egress filtering."""
        if content_type == ContentType.TEXT:
            if not isinstance(content, str):
                return content
            # Hard Rule: Real user tweets are untouched; phantom tweets have style guard applied
            if is_phantom:
                return await self.style_guard.apply_noise(content)
            return content

        elif content_type == ContentType.IMAGE:
            if not isinstance(content, bytes):
                return content
            stripped = await self.metadata_stripper.strip_image_metadata(content)
            return await self.perturbation_engine.perturb_image(stripped, destination="twitter")

        elif content_type == ContentType.AUDIO:
            if not isinstance(content, bytes):
                return content
            return await self.metadata_stripper.strip_audio_metadata(content)

        elif content_type in (ContentType.VIDEO, ContentType.RAW):
            if not isinstance(content, bytes):
                return content
            return await self.perturbation_engine.perturb_video(content, destination="twitter")

        return content

    def get_phantom_actions(self) -> List[Dict[str, Any]]:
        """Scheduled phantom activities (decoy trend interaction and timeline noise)."""
        return [
            {"action": "search_trends", "queries": ["#AstronomyDay", "#VintageCars", "#CoffeeLovers"]},
            {"action": "timeline_scroll", "duration_sec": 30, "topic": "sports"},
            {"action": "like_decoy_posts", "count": 3, "tags": ["nature", "hiking"]},
        ]
