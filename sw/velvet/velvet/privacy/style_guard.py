"""
Stylometric defense for auto-generated text.
"""

import logging
import random
import re
from typing import Any

logger = logging.getLogger(__name__)

SYNONYM_MAP = {
    "quick": ["rapid", "swift", "prompt"],
    "quickly": ["promptly", "rapidly", "swiftly"],
    "start": ["begin", "commence", "initiate"],
    "started": ["began", "commenced", "initiated"],
    "stop": ["halt", "terminate", "cease"],
    "error": ["issue", "fault", "discrepancy"],
    "errors": ["issues", "faults", "discrepancies"],
    "user": ["operator", "client", "requester"],
    "important": ["crucial", "critical", "essential"],
    "help": ["assist", "aid", "support"],
    "create": ["generate", "produce", "instantiate"],
    "created": ["generated", "produced", "instantiated"],
    "delete": ["remove", "purge", "clear"],
    "deleted": ["removed", "purged", "cleared"],
    "check": ["verify", "inspect", "examine"],
    "checked": ["verified", "inspected", "examined"],
    "find": ["locate", "discover", "identify"],
    "found": ["located", "discovered", "identified"],
    "use": ["utilize", "apply", "employ"],
    "used": ["utilized", "applied", "employed"],
    "system": ["framework", "platform", "infrastructure"],
    "complete": ["finished", "fulfilled", "finalized"],
    "completed": ["finished", "fulfilled", "finalized"],
}


class StyleGuard:
    """
    Applies subtle writing style variations to AUTO-GENERATED text only.
    Never modifies text that the user wrote themselves.
    """
    
    def __init__(self, strength: Any):
        """
        Initialize with a global PrivacyStrength.
        """
        self.strength = strength
        self.enabled = True
        
    async def apply_noise(self, text: str) -> str:
        """
        Apply synonym substitution and stylometric noise based on configured strength.
        
        Args:
            text: The auto-generated text to modify.
            
        Returns:
            The stylometrically modified text.
        """
        if not self.enabled or not text:
            return text

        strength_val = getattr(self.strength, "value", str(self.strength)).lower()
        if strength_val == "off":
            return text

        rate_map = {
            "low": 0.15,
            "medium": 0.30,
            "high": 0.50,
            "paranoid": 0.70,
        }
        sub_rate = rate_map.get(strength_val, 0.25)
        logger.debug(f"[StyleGuard] Applying stylometric noise at strength {strength_val} (rate: {sub_rate})")

        words = text.split(" ")
        modified_words = []

        for word in words:
            # Strip punctuation for lookup
            clean_word = re.sub(r"[^\w]", "", word).lower()
            if clean_word in SYNONYM_MAP and random.random() < sub_rate:
                candidates = SYNONYM_MAP[clean_word]
                replacement = random.choice(candidates)
                # Preserve capitalization
                if word and word[0].isupper():
                    replacement = replacement.capitalize()
                # Re-attach trailing punctuation
                trailing = "".join(c for c in word if not c.isalnum())
                modified_words.append(replacement + trailing)
            else:
                modified_words.append(word)

        return " ".join(modified_words)
