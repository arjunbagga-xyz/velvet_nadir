import asyncio
import unittest
import base64
import numpy as np
import cv2
from velvet.fabric import get_fabric, MessageType, VelvetMessage
from velvet.main import start_velvet, stop_velvet
from velvet.config import get_config

class TestMeshIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # We need two independent fabrics potentially?
        # Zenoh python binding is global singleton usually unless configured carefully.
        # Actually, for this test, we can just use ONE fabric and verify publish/subscribe works.
        # But to test "Universal Node" logic, we ideally want separate processes.
        # Since multiprocess testing is hard in unittest, we will simulate the flow:
        # 1. Start Gateway (subscribes to events)
        # 2. Mock a Client publishing events
        
        self.config = get_config()
        self.gateway = await start_velvet(
            use_llm=False,
            modules=["gateway"]
        )
        self.fabric = get_fabric()

    async def asyncTearDown(self):
        await stop_velvet()

    async def test_vision_streaming(self):
        """Verify Gateway receives vision events from a 'Client'."""
        # Mock a frame
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.rectangle(img, (20, 20), (80, 80), (0, 255, 0), -1)
        _, buffer = cv2.imencode('.jpg', img)
        img_b64 = base64.b64encode(buffer).decode('utf-8')
        
        # Publish as if from a remote node
        await self.fabric.publish(
            MessageType.VISION_EVENT.value,
            {
                "event": "motion_detected",
                "score": 0.8,
                "image": img_b64
            }
        )
        
        # We need to verify Gateway received it.
        # Gateway routes to Yi -> Po.
        # Po.vision_monitor._important_frame should be updated.
        
        # Allow async propagation
        await asyncio.sleep(1)
        
        # Check Po state
        po = self.gateway.yi.po
        self.assertIsNotNone(po.vision_monitor._important_frame)
        self.assertEqual(po.vision_monitor._important_frame.shape, (100, 100, 3))

    async def test_audio_streaming(self):
        """Verify Gateway receives audio transcripts."""
        # Publish transcript
        await self.fabric.publish(
            MessageType.TRANSCRIPT.value,
            {"text": "Hello from the mesh", "is_final": True}
        )
        
        await asyncio.sleep(1)
        
        # Verify context update
        messages = self.gateway.context.working_memory.conversation_buffer
        self.assertTrue(len(messages) > 0)
        self.assertTrue(any(msg["content"] == "Hello from the mesh" for msg in messages))

if __name__ == "__main__":
    unittest.main()
