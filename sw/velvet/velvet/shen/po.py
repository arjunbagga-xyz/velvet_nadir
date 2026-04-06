import asyncio
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from loguru import logger

from velvet.config import get_config
from velvet.fabric import get_fabric, MessageType

class VisionMonitor:
    """
    Background monitor that watches the webcam and detects important changes.
    """
    def __init__(self, camera_id: int | None = None, threshold: int | None = None):
        config = get_config()
        vision_cfg = config.vision
        self.camera_id = camera_id if camera_id is not None else vision_cfg.camera_index
        self.threshold = threshold if threshold is not None else vision_cfg.motion_threshold
        self._rate_limit_sec = vision_cfg.rate_limit_sec
        self._log_level = vision_cfg.log_level.upper()
        self.running = False
        self._cap = None
        self._last_frame = None
        self._important_frame = None
        self._thread = None
        self._last_event_time = 0.0
        
    def start(self):
        if self.running: return
        self.running = True
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.get_event_loop()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(f"[Po] VisionMonitor started on camera {self.camera_id}")

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._cap:
            self._cap.release()

    def _run(self):
        self._cap = cv2.VideoCapture(self.camera_id)
        if not self._cap.isOpened():
            logger.error(f"[Po] Failed to open camera {self.camera_id}")
            self.running = False
            return

        fabric = get_fabric()
        
        while self.running:
            ret, frame = self._cap.read()
            if not ret:
                time.sleep(1.0)
                continue

            # Basic Change Detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            if self._last_frame is None:
                self._last_frame = gray
                continue

            frame_delta = cv2.absdiff(self._last_frame, gray)
            thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            
            motion_score = np.sum(thresh)
            
            if motion_score > self.threshold:
                now = time.time()
                if now - self._last_event_time < self._rate_limit_sec:
                    self._last_frame = gray
                    time.sleep(1.0 / get_config().vision.fps)
                    continue
                self._last_event_time = now
                
                if self._log_level == "INFO":
                    logger.info(f"[Po] Visual change detected (score: {motion_score})")
                else:
                    logger.debug(f"[Po] Visual change detected (score: {motion_score})")
                self._important_frame = frame.copy()
                
                # Encode frame for transmission
                ret, buffer = cv2.imencode('.jpg', frame)
                if ret:
                    import base64
                    img_b64 = base64.b64encode(buffer).decode('utf-8')
                    
                    if hasattr(self, '_loop') and self._loop:
                        asyncio.run_coroutine_threadsafe(
                            fabric.publish(
                                MessageType.VISION_EVENT.value,
                                {
                                    "event": "motion_detected", 
                                    "score": float(motion_score),
                                    "image": img_b64
                                }
                            ),
                            self._loop
                        )

            self._last_frame = gray
            time.sleep(1.0 / get_config().vision.fps)

    def get_current_frame(self) -> Optional[np.ndarray]:
        return self._important_frame

class VisionEngine:
    """
    Semantic analysis for vision data.
    """
    def __init__(self, model_name: str, base_url: str):
        from velvet.llm import create_llm_adapter
        from velvet.config import get_config
        config = get_config()
        self.adapter = create_llm_adapter(
            adapter_type=config.llm.adapter,
            model=model_name, 
            base_url=base_url
        )
        
    async def analyze(self, frame: np.ndarray, prompt: str = "What is in this image?") -> str:
        # 1. Encode frame to base64
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            return "Failed to encode image."
            
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # 2. Call VLM
        messages = [{"role": "user", "content": prompt}]
        response = await self.adapter.generate(messages, images=[img_base64])
        
        return response.text

class Po:
    """
    Po (魄): The Corporeal Soul / Body.
    
    Handles Edge capabilities: Sensation (Vision/Audio), Reflexes, and Motor Control.
    Supports both hardcoded regex reflexes and learned reflexes (taught by Fuxi).
    """
    
    async def on_vision_event(self, image_b64: str, score: float):
        """Handle a vision event from a remote monitor."""
        import base64
        try:
            # Decode base64 image back to numpy array
            img_bytes = base64.b64decode(image_b64)
            nparr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is not None:
                self.vision_monitor._important_frame = frame
                logger.debug(f"[Po] Updated remote frame (score: {score})")
        except Exception as e:
            logger.error(f"[Po] Failed to decode remote frame: {e}")

    def __init__(self, start_vision_monitor: bool = True):
        self.config = get_config()
        
        self.vision_engine = None
        
        # Initialize Monitor
        self.vision_monitor = VisionMonitor()
        if start_vision_monitor:
            self.vision_monitor.start()
        else:
            logger.info("[Po] Vision monitor disabled (remote mode)")
        
        # Initialize Vision Engine (VLM)
        vision_cfg = self.config.llm
        self.vision_engine = VisionEngine(
            model_name=vision_cfg.vision_model,
            base_url=vision_cfg.base_url
        )

        # Learned reflexes (taught by Fuxi from Xi batch analysis)
        self._learned_reflexes: list[LearnedReflex] = []
        self._reflexes_path = Path.home() / ".velvet" / "reflexes.json"
        self._load_reflexes()

    def learn_reflex(self, user_input: str, skill_name: str,
                     params: dict | None = None):
        """
        Learn a new reflex pattern (called by Fuxi).

        If the pattern already exists, reinforces its confidence.
        Persists to disk immediately.
        """
        normalized = user_input.lower().strip()

        # Check if we already have this pattern
        for reflex in self._learned_reflexes:
            if normalized in reflex.examples or reflex.pattern == normalized:
                reflex.confidence = min(1.0, reflex.confidence + 0.1)
                if normalized not in reflex.examples:
                    reflex.examples.append(normalized)
                self._save_reflexes()
                logger.info(f"[Po] Reinforced reflex: '{normalized}' → {skill_name} "
                          f"(conf={reflex.confidence:.2f})")
                return

        # New reflex
        reflex = LearnedReflex(
            pattern=normalized,
            skill_name=skill_name,
            params_template=params or {},
            confidence=0.5,
            examples=[normalized],
        )
        self._learned_reflexes.append(reflex)
        self._save_reflexes()
        logger.info(f"[Po] Learned new reflex: '{normalized}' → {skill_name}")

    async def reflex(self, stimulus: str) -> str:
        """
        Fast path reaction — hard-wired + learned reflexes.
        No LLM call. Complex requests go to Hun.
        """
        import re
        stimulus_lower = stimulus.lower().strip()
        fabric = get_fabric()

        # 1. Regex Reflexes (Hardware Fast Path)
        # "Turn on/off <device>"
        match = re.search(r"turn (on|off) (.+)", stimulus_lower)
        if match:
            state = match.group(1)
            device = match.group(2)
            await fabric.publish(
                MessageType.SKILL_REQUEST.value,
                {
                    "skill": "home_control",
                    "params": {"device": device, "state": state},
                    "source": "PoReflex"
                }
            )
            return f"Turning {state} {device}."

        # "Time"
        if "time" in stimulus_lower and "what" in stimulus_lower:
            from datetime import datetime
            now = datetime.now().strftime("%I:%M %p")
            return f"It is {now}."
            
        # "Stop"
        if stimulus_lower in ["stop", "cancel", "shut up"]:
            await fabric.publish(MessageType.CANCEL_REQUEST.value, {"source": "PoReflex"})
            return "Stopping."

        # 2. Learned Reflexes (taught by Fuxi)
        learned = self._match_learned(stimulus_lower)
        if learned:
            logger.info(f"[Po] Learned reflex matched: '{stimulus_lower}' → {learned.skill_name} "
                       f"(conf={learned.confidence:.2f})")
            await fabric.publish(
                MessageType.SKILL_REQUEST.value,
                {
                    "skill": learned.skill_name,
                    "params": learned.params_template,
                    "source": "PoLearnedReflex",
                }
            )
            return f"Got it. (Learned reflex: {learned.skill_name})"

        # No reflex match — return None to signal Yi to route to Hun
        return None

    def _match_learned(self, stimulus: str) -> 'LearnedReflex | None':
        """Match stimulus against learned reflexes (substring similarity)."""
        best_match = None
        best_score = 0.0

        for reflex in self._learned_reflexes:
            if reflex.confidence < 0.4:
                continue

            # Check exact match against examples
            if stimulus in reflex.examples:
                return reflex

            # Check substring containment (both directions)
            for example in reflex.examples:
                # Simple similarity: how much of the example is in the stimulus
                if example in stimulus or stimulus in example:
                    score = reflex.confidence
                    if score > best_score:
                        best_score = score
                        best_match = reflex

        # Only return if confidence is reasonable
        if best_match and best_score >= 0.6:
            return best_match
        return None

    def _load_reflexes(self):
        """Load learned reflexes from disk."""
        import json
        if not self._reflexes_path.exists():
            return
        try:
            with open(self._reflexes_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._learned_reflexes = [
                LearnedReflex.from_dict(d) for d in data
            ]
            logger.info(f"[Po] Loaded {len(self._learned_reflexes)} learned reflexes")
        except Exception as e:
            logger.error(f"[Po] Failed to load reflexes: {e}")

    def _save_reflexes(self):
        """Save learned reflexes to disk."""
        import json
        try:
            self._reflexes_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._reflexes_path, "w", encoding="utf-8") as f:
                json.dump(
                    [r.to_dict() for r in self._learned_reflexes],
                    f, indent=2, ensure_ascii=False,
                )
        except Exception as e:
            logger.error(f"[Po] Failed to save reflexes: {e}")


@dataclass
class LearnedReflex:
    """A learned reflex pattern (taught by Fuxi from Xi batch analysis)."""
    pattern: str                # Primary trigger pattern
    skill_name: str             # Skill to invoke
    params_template: dict       # Default params
    confidence: float = 0.5     # 0=untrained, 1=very reliable
    examples: list[str] = field(default_factory=list)  # All known trigger phrases

    def to_dict(self) -> dict:
        return {
            "pattern": self.pattern,
            "skill_name": self.skill_name,
            "params_template": self.params_template,
            "confidence": self.confidence,
            "examples": self.examples,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'LearnedReflex':
        return cls(
            pattern=data.get("pattern", ""),
            skill_name=data.get("skill_name", ""),
            params_template=data.get("params_template", {}),
            confidence=data.get("confidence", 0.5),
            examples=data.get("examples", []),
        )

