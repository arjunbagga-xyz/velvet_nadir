"""
Xiàng (相): Physiognomy / People Recognition.

Extracts facial and voice embeddings from raw sensor data,
identifies people against Jing's memory, and manages identity contexts.
"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, TYPE_CHECKING
from loguru import logger

from velvet.config import get_config

if TYPE_CHECKING:
    from velvet.shen.jing import Jing

# Optional imports for models
try:
    from facenet_pytorch import MTCNN, InceptionResnetV1
    import torch
    HAS_FACENET = True
except ImportError:
    HAS_FACENET = False

try:
    from resemblyzer import VoiceEncoder
    HAS_RESEMBLYZER = True
except ImportError:
    HAS_RESEMBLYZER = False


@dataclass
class PersonRecord:
    """Record of an identified or unidentified person."""
    name: str = "unknown"
    confidence: float = 0.0
    face_embedding: Optional[np.ndarray] = None
    voice_embedding: Optional[np.ndarray] = None


class XiangEngine:
    """
    Xiàng (相) Engine: Extracts biometrics and queries Jing memory 
    to recognize known people.
    """
    
    def __init__(self, jing: Optional['Jing'] = None):
        self._jing = jing
        self._config = get_config().xiang
        self._enabled = self._config.enabled
        
        self.device = None
        if HAS_FACENET:
            self.device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
            
        self._mtcnn = None
        self._resnet = None
        self._voice_encoder = None
        
        if self._enabled:
            self._init_models()

    def _init_models(self):
        if HAS_FACENET and self._config.face_model == "facenet":
            try:
                self._mtcnn = MTCNN(keep_all=True, device=self.device)
                self._resnet = InceptionResnetV1(pretrained='vggface2').eval().to(self.device)
                logger.info("[Xiang] Face recognition (facenet) initialized.")
            except Exception as e:
                logger.error(f"[Xiang] Failed to load facenet models: {e}")
        else:
            logger.info("[Xiang] facenet_pytorch disabled or not installed.")
            
        if HAS_RESEMBLYZER and self._config.voice_model == "resemblyzer":
            try:
                self._voice_encoder = VoiceEncoder()
                logger.info("[Xiang] Voice recognition (resemblyzer) initialized.")
            except Exception as e:
                logger.error(f"[Xiang] Failed to load resemblyzer model: {e}")
        else:
            logger.info("[Xiang] resemblyzer disabled or not installed.")

    async def identify_faces(self, frame_rgb: np.ndarray) -> list[PersonRecord]:
        """Extract faces from an RGB frame and identify against Jing."""
        if not self._enabled or not self._mtcnn or not self._resnet:
            return []
            
        try:
            from PIL import Image
            import torch
            
            img = Image.fromarray(frame_rgb)
            faces = self._mtcnn(img)
            
            if faces is None:
                return []
                
            records = []
            for face_tensor in faces:
                # Get embeddings (512-d)
                emb_tensor = self._resnet(face_tensor.unsqueeze(0).to(self.device))
                emb = emb_tensor.detach().cpu().numpy()[0]
                
                # Query Jing
                person = await self._query_jing_identity(emb, "face")
                if not person:
                    person = PersonRecord(face_embedding=emb)
                records.append(person)
                
            return records
        except Exception as e:
            logger.error(f"[Xiang] Face identification failed: {e}")
            return []

    async def identify_voice(self, audio_data: np.ndarray, sample_rate: int) -> Optional[PersonRecord]:
        """Extract voice embedding from audio waveform and identify."""
        if not self._enabled or not self._voice_encoder:
            return None
            
        try:
            # Resemblyzer expects preprocessed float32 audio
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32) / np.iinfo(audio_data.dtype).max
                
            # VoiceEncoder expects ~16k mono audio. For strictness, you'd resample if sample_rate != 16000
            emb = self._voice_encoder.embed_utterance(audio_data)
            
            person = await self._query_jing_identity(emb, "voice")
            if not person:
                return PersonRecord(voice_embedding=emb)
            return person
            
        except Exception as e:
            logger.error(f"[Xiang] Voice identification failed: {e}")
            return None

    async def _query_jing_identity(self, embedding: np.ndarray, modality: str) -> Optional[PersonRecord]:
        """Find the nearest known person identity using Jing."""
        if not self._jing:
            return None
            
        result = await self._jing.recall_by_embedding(
            embedding.tolist(), 
            type_tag=self._config.memory_type_tag,
            modality=modality
        )
        
        if result and result.get('confidence', 0) >= self._config.recognition_threshold:
            return PersonRecord(
                name=result['name'],
                confidence=result['confidence'],
                face_embedding=embedding if modality == "face" else None,
                voice_embedding=embedding if modality == "voice" else None
            )
        return None
