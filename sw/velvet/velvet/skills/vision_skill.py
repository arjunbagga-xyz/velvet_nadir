from loguru import logger
import numpy as np
import cv2
import base64

from ..skills import (
    skill,
    SkillCategory,
    SkillParameter,
    SkillResult,
    AutonomyLevel,
)

@skill(
    name="look",
    description="Capture and analyze the current scene through the camera.",
    category=SkillCategory.PERCEPTION,
    parameters=[
        SkillParameter("detail", "string", "Level of detail for analysis (standard, focused)", required=False, default="standard")
    ],
    autonomy=AutonomyLevel.LEVEL_1,
    tags=["vision", "perception", "capture"]
)
async def look(detail: str = "standard") -> SkillResult:
    """Capture a frame and describe it."""
    try:
        from ..gateway import get_gateway
        po = get_gateway().yi.po
        
        # Get the latest frame from vision monitor
        frame = po.vision_monitor.get_current_frame()
        if frame is None:
            return SkillResult.fail("No significant visual data captured yet. Is the camera active?")
        
        # Analyze with VLM
        if po.vision_engine:
            description = await po.vision_engine.analyze(frame, prompt="Describe what you see in this scene concisely.")
        else:
            description = "I captured an image but no vision model is loaded for analysis."
            
        return SkillResult.ok(
            data={"description": description},
            speak=f"I'm looking. {description}",
            display={"markdown": f"### Scene Analysis\n\n{description}"}
        )
        
    except Exception as e:
        logger.error(f"Error in look() skill: {e}")
        return SkillResult.fail(f"Vision error: {str(e)}")

@skill(
    name="monitor_scene",
    description="Control the background vision monitoring (start, stop, or check status).",
    category=SkillCategory.PERCEPTION,
    parameters=[
        SkillParameter("action", "string", "The action to perform: 'start', 'stop', or 'status'", required=True)
    ],
    autonomy=AutonomyLevel.LEVEL_1,
    tags=["vision", "monitor", "control"]
)
async def monitor_scene(action: str) -> SkillResult:
    """Control the vision monitor."""
    try:
        from ..gateway import get_gateway
        po = get_gateway().yi.po
        
        action = action.lower()
        if action == "start":
            po.vision_monitor.start()
            return SkillResult.ok(speak="Vision monitor started.")
        elif action == "stop":
            po.vision_monitor.stop()
            return SkillResult.ok(speak="Vision monitor stopped.")
        elif action == "status":
            running = po.vision_monitor.running
            return SkillResult.ok(
                data={"running": running},
                speak=f"The vision monitor is currently {'active' if running else 'inactive'}."
            )
        else:
            return SkillResult.fail(f"Unknown action: {action}")
            
    except Exception as e:
        logger.error(f"Error in monitor_scene() skill: {e}")
        return SkillResult.fail(f"Error controlling monitor: {str(e)}")
