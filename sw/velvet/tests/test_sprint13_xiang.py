"""
Tests for Phase 2: Xiàng (相) — People Recognition.
"""

import sys
from unittest.mock import AsyncMock, patch, MagicMock

# Mock torch if not installed
try:
    import torch
except ImportError:
    sys.modules["torch"] = MagicMock()

import pytest
import numpy as np

from velvet.shen.xiang import XiangEngine, PersonRecord
from velvet.shen.jing import Jing
from velvet.config import get_config

@pytest.fixture
def jing_with_people():
    jing = Jing()
    # Force _mem to None so it uses our local fallback logic
    jing._mem = None
    
    # add directly to mock storage
    if not hasattr(jing, '_mock_people'):
        jing._mock_people = []
    
    # Store a test person
    face_emb = np.array([0.5] * 512)
    voice_emb = np.array([0.2] * 256)
    
    jing._mock_people.append({
        "name": "tester",
        "type": "person",
        "face_embedding": face_emb.tolist(),
        "voice_embedding": voice_emb.tolist()
    })
    return jing


@pytest.fixture
def mock_xiang(jing_with_people):
    # Mock config to enable and bypass real models
    cfg = get_config().xiang
    cfg.enabled = True
    cfg.recognition_threshold = 0.8
    
    xiang = XiangEngine(jing=jing_with_people)
    return xiang


@pytest.mark.asyncio
async def test_jing_recall_by_embedding(jing_with_people):
    """Jing should find the right person given a similar embedding."""
    query_emb = np.array([0.49] * 512).tolist()
    
    result = await jing_with_people.recall_by_embedding(query_emb, type_tag="person", modality="face")
    assert result is not None
    assert result["name"] == "tester"
    # high similarity because [0.49] * 512 and [0.5] * 512 have cos sim ~1.0
    assert result["confidence"] > 0.99


@pytest.mark.asyncio
async def test_jing_recall_unknown(jing_with_people):
    """Jing shouldn't return a match if empty or completely disjoint, though 
    with cosine sim it might. We'll test with a strongly negative vector."""
    query_emb = np.array([-0.5] * 512).tolist()
    result = await jing_with_people.recall_by_embedding(query_emb, type_tag="person", modality="face")
    
    # Cosine similarity will be around -1.0, which means best_score gets set depending on our logic.
    if result:
        assert result["confidence"] <= 0.0


@pytest.mark.asyncio
async def test_xiang_identify_faces_known(mock_xiang):
    # Mock mtcnn and resnet
    mock_xiang._mtcnn = MagicMock()
    # It returns a list of faces
    # Since resnet will be applied on every face, let's just make it return a dummy list
    mock_tensor = MagicMock()
    mock_tensor.unsqueeze.return_value.to.return_value = "dummy_face"
    mock_xiang._mtcnn.return_value = [mock_tensor]
    
    mock_xiang._resnet = MagicMock()
    # Return embedding close to "tester"
    emb = np.array([[0.5] * 512]) # Batch dim
    class DummyResnetResult:
        def detach(self): return self
        def cpu(self): return self
        def numpy(self): return emb
    mock_xiang._resnet.return_value = DummyResnetResult()
    
    with patch("PIL.Image.fromarray") as mock_img:
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        records = await mock_xiang.identify_faces(frame)
        
        assert len(records) == 1
        assert records[0].name == "tester"
        assert records[0].confidence > 0.9


@pytest.mark.asyncio
async def test_xiang_identify_faces_unknown(mock_xiang):
    mock_xiang._mtcnn = MagicMock()
    mock_tensor = MagicMock()
    mock_tensor.unsqueeze.return_value.to.return_value = "dummy"
    mock_xiang._mtcnn.return_value = [mock_tensor]
    
    mock_xiang._resnet = MagicMock()
    # Return orthogonal embedding
    emb = np.array([[-0.5] * 512]) # dot product is negative -> sim < threshold
    class DummyResnetResult:
        def detach(self): return self
        def cpu(self): return self
        def numpy(self): return emb
    mock_xiang._resnet.return_value = DummyResnetResult()
    
    with patch("PIL.Image.fromarray") as mock_img:
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        records = await mock_xiang.identify_faces(frame)
        
        assert len(records) == 1
        # Threshold was 0.8, confidence is ~ -1.0, so it fails matching
        assert records[0].name == "unknown"
        assert records[0].face_embedding is not None


@pytest.mark.asyncio
async def test_xiang_identify_voice_known(mock_xiang):
    mock_xiang._voice_encoder = MagicMock()
    mock_xiang._voice_encoder.embed_utterance.return_value = np.array([0.2] * 256)
    
    # Provide float32 audio
    audio = np.zeros(16000, dtype=np.float32)
    record = await mock_xiang.identify_voice(audio, 16000)
    
    assert record is not None
    assert record.name == "tester"
    assert record.confidence > 0.9
