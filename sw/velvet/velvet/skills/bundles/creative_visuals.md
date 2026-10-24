---
name: creative_visuals
description: Generate images, UI mockups, diagrams, and visual assets using cloud diffusion models or local renderers.
category: Creative
autonomy_required: LEVEL_1
parameters: prompt:string:Detailed descriptive text prompt for image generation, style:string:Visual style (photorealistic, ui_mockup, diagram, anime, isometric), aspect_ratio:string:Image dimensions/aspect ratio (1:1, 16:9, 4:3), output_filename:string:Target filename to save in workspace or artifacts
tags: [creative, image, visuals, diffusion, design, ui, mockup, generation]
---

# Creative Visuals & Asset Generation

This skill generates high-quality images, UI mockups, architecture diagrams, and creative visual assets by interfacing with cloud diffusion endpoints or local renderers.

## Generation Capabilities

1. **UI Mockups & Web Design**:
   - Style: `ui_mockup`
   - Generates clean, modern web or mobile application interfaces without surrounding device frames. Focuses on rich aesthetics, vibrant palettes, and sleek layouts.

2. **Architecture & System Diagrams**:
   - Style: `diagram`
   - Creates clean isometric or block diagrams representing distributed networks, agent hierarchies, or data pipelines.

3. **Photorealistic & Artistic Assets**:
   - Style: `photorealistic`, `anime`, `isometric`
   - Generates custom illustrations, icons, and visual assets tailored to user specifications.

## Execution Workflow
1. **Prompt Enhancement**: Refine `{prompt}` to incorporate best practices for `{style}` (lighting, composition, color harmony).
2. **Model Dispatch**:
   - Route request to cloud diffusion API via CredentialPool or local Stable Diffusion / Flux backend if available on mesh GPU nodes.
3. **Asset Persistence**:
   - Save generated image to `{output_filename}` within the active workspace or `<appDataDir>/brain/<conversation-id>/` artifacts directory.

## Output Format
Return markdown embedding the generated image:
- Clickable markdown image link: `![{prompt}](file:///{output_filename})`
- Metadata summary (Style, Resolution, File Path)
