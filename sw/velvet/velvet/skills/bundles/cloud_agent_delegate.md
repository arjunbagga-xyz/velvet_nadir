---
name: cloud_agent_delegate
description: Delegate complex, resource-intensive reasoning or specialized tasks to external cloud agent platforms via UniversalCloudLLMAdapter and ACP.
category: Orchestration
autonomy_required: LEVEL_2
parameters: target_platform:string:External agent platform (google, openrouter, nvidia, custom_acp), task_prompt:string:The task description and instructions to delegate, context_payload:string:Supporting context or data required for the task, timeout_seconds:int:Maximum wait time in seconds (default 120)
tags: [orchestration, delegation, cloud, acp, multi-agent, universal_llm]
---

# Cloud Agent Delegation (ACP & Universal LLM)

This skill enables Velvet to delegate sub-tasks or complex reasoning workloads to external cloud agent platforms and LLMs via `UniversalCloudLLMAdapter` or Agent Communication Protocol (ACP) endpoints.

## Delegation Protocol

1. **Privacy & Scrambling Verification**:
   - Before dispatching any prompt to an external cloud provider, verify that PrivacyGuard has classified the content.
   - If `privacy_level` is `RESTRICTED`, abort delegation immediately.
   - For `INTERNAL` or `CONFIDENTIAL` levels, ensure anonymization/scrambling passes have been applied.

2. **Route Selection**:
   - For `google`: Route via `UniversalCloudLLMAdapter(provider="google", model="gemini-2.5-flash")` or configured Gemini model.
   - For `nvidia`: Route via `UniversalCloudLLMAdapter(provider="nvidia", model="nvidia/llama-3.3-nemotron-super-49b-v1")`.
   - For `openrouter`: Route via OpenRouter API endpoint for specialized models.
   - For `custom_acp`: Dispatch JSON-RPC / REST envelope over configured ACP gateway.

3. **Execution & Monitoring**:
   - Transmit `{task_prompt}` along with sanitized `{context_payload}`.
   - Monitor execution up to `{timeout_seconds}`.
   - If rate limits (HTTP 429) occur, CredentialPool will automatically trigger cooldowns and attempt fallback keys.

## Output Synthesis
Return the external agent's response formatted in standard markdown:
- **Delegation Target**: Provider and Model ID
- **Execution Status**: Success / Timeout / Fallback
- **Result Output**: Full synthesized response from the delegated agent
