"""
Main entry point for Velvet Nadir.

Provides:
- CLI interface for running the system
- Interactive console mode for testing
- Live audio mode with real microphone input
"""

__all__ = [
    "setup_logging",
    "start_velvet",
    "stop_velvet",
    "interactive_console",
    "main",
]

import asyncio
import sys
from pathlib import Path
from loguru import logger

from .config import get_config, load_config
from .fabric import init_fabric, get_fabric
from .context import init_context_manager, get_context_manager
from .skills import get_skill_registry
from .gateway import init_gateway, get_gateway, Gateway
from .monitors import MockAudioMonitor, MockTTSOutput, AudioMonitor, RealTTSOutput
from .shen.po import VisionMonitor


def setup_logging(level: str = "INFO") -> None:
    """Configure logging with loguru."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    )


async def start_velvet(
    use_llm: bool = False,
    llm_model: str | None = None,
    llm_adapter: str | None = None,
    modules: list[str] | None = None,
    connect_to: list[str] | None = None,
) -> Gateway | None:
    """
    Start Velvet systems.
    
    modules: List of capabilities to run (gateway, audio, vision, discovery).
    connect_to: List of Zenoh peers to connect to (if acting as a Client Node).
    """
    config = get_config()
    
    # Auto-provision TLS certificates
    try:
        from .security import CertManager
        cert_mgr = CertManager(config.security.certs_dir)
        cert_mgr.ensure_ca()
        
        if not cert_mgr.has_node_cert(config.device_id):
            cert_mgr.issue_node_cert(config.device_id)
        
        # Auto-populate Zenoh TLS config from cert paths
        paths = cert_mgr.get_tls_paths(config.device_id)
        config.zenoh.tls_enabled = True
        config.zenoh.tls_root_ca = paths["root_ca"]
        config.zenoh.tls_server_cert = paths["cert"]
        config.zenoh.tls_server_key = paths["key"]
        config.zenoh.tls_mtls_enabled = True
        logger.info(f"TLS auto-provisioned for {config.device_id}")
    except Exception as e:
        logger.warning(f"TLS auto-provisioning failed (non-fatal): {e}")
    
    # Initialize communication fabric
    fabric = await init_fabric(
        device_id=config.device_id,
        mode=config.zenoh.mode,
        connect=connect_to or config.zenoh.connect or None,
        listen=config.zenoh.listen or None,
    )

    # Initialize Hardware Registry & Register Host
    try:
        from .devices import init_registry, create_local_device, DeviceType
        registry = await init_registry(with_fabric=True)
        
        # Create and register local device
        local_device = create_local_device(
            device_id=config.device_id,
            name="Velvet Host",
            device_type=DeviceType.COMPUTE
        )
        await registry.register(local_device)
        registry.start_heartbeat(local_device.device_id)
        logger.info(f"Host registered: {local_device.device_id}")
    except Exception as e:
        logger.warning(f"Failed to register host device: {e}")
    
    # Initialize persistent memory
    memory = None
    try:
        from .memory import init_memory
        memory = await init_memory(config.storage.data_dir)
        logger.info(f"Persistent memory ready at {config.storage.data_dir}")
    except Exception as e:
        logger.warning(f"Could not initialize persistent memory: {e}")
    
    # Initialize context manager with persistence
    from .context import init_context_manager_with_persistence
    ctx_mgr = await init_context_manager_with_persistence(
        enabled_tracks=config.context.tracks,
        memory=memory,
    )
    
    # Setup LLM inference if requested
    llm_inference = None
    if use_llm:
        try:
            from .llm import create_llm_adapter, MeshLLMAdapter, VELVET_SYSTEM_PROMPT
            from .services.llm_service import LLMProvider
            
            adapter_type = llm_adapter or config.llm.adapter
            model = llm_model or config.llm.model
            
            # Build adapter kwargs based on type
            adapter_kwargs: dict = {"model": model}
            if adapter_type in ("ollama", "vllm"):
                adapter_kwargs["base_url"] = config.llm.base_url
            elif adapter_type == "llama.cpp":
                adapter_kwargs = {"model_path": model}
            elif adapter_type == "google":
                adapter_kwargs["api_key"] = config.llm.google_api_key
            
            # Create the adapter via factory
            adapter = create_llm_adapter(adapter_type, **adapter_kwargs)
            
            # Try to wrap in Mesh service for smart routing
            try:
                llm_service = LLMProvider()
                await llm_service.start()
                adapter = MeshLLMAdapter(service_provider=llm_service)
                logger.info(f"LLM enabled: Mesh Mode ({adapter_type}/{model})")
            except Exception as mesh_err:
                logger.warning(f"Mesh LLM unavailable ({mesh_err}), using direct adapter")
                logger.info(f"LLM enabled: Direct Mode ({adapter_type}/{model})")
            
            async def llm_inference_fn(context: str, messages: list, tools: list | None):
                full_messages = [
                    {"role": "system", "content": VELVET_SYSTEM_PROMPT + "\n\n" + context}
                ] + messages
                response = await adapter.generate(full_messages, tools=tools)
                return response.text
                
            llm_inference = llm_inference_fn
        except Exception as e:
            logger.warning(f"Could not setup LLM: {e}")
    
    # Determine what to run
    monolithic = modules is None
    run_discovery = monolithic or (modules and "discovery" in modules)
    run_vision = modules and "vision" in modules
    run_audio = monolithic or (modules and "audio" in modules)
    run_gateway = monolithic or (modules and "gateway" in modules)
    
    # 1. Discovery Service (and Registry)
    if run_discovery:
        try:
            from .scan import start_discovery_service
            
            start_discovery_service()
            logger.info("Discovery service and Hardware Registry started")
        except Exception as e:
            logger.warning(f"Could not start discovery service: {e}")

    # 2. Standalone Vision (if requested explicitly)
    if run_vision:
        # If running just vision, we start the monitor here.
        # It publishes events to fabric.
        try:
            vm = VisionMonitor()
            vm.start()
            logger.info("Standalone Vision Monitor started")
        except Exception as e:
            logger.error(f"Failed to start vision monitor: {e}")

    # 3. Standalone Audio (Microphone + Speaker)
    if run_audio and not run_gateway:
        # If running gateway, it usually manages audio context, but for now
        # we treat audio as a separate monitor even on host?
        # Actually, if run_gateway is False (Satellite Node), we MUST start AudioMonitor manually.
        try:
            am = AudioMonitor(enabled=config.audio.enabled)
            await am.start()
            
            # Also start TTS Listener to speak responses
            tts = RealTTSOutput() if config.audio.use_real_audio else MockTTSOutput()
            await tts.start()
            
            logger.info("Standalone Audio Monitor (Ears & Mouth) started")
        except Exception as e:
            logger.error(f"Failed to start audio monitor: {e}")

    # 3. Gateway (The Brain)
    gateway = None
    if run_gateway:
        # If monolithic, Gateway owns vision (vision_enabled=True)
        # If split, vision is external (vision_enabled=False)
        vision_enabled = monolithic
        
        # Initialize gateway (reads max_workers + autonomy from config)
        from .skills import AutonomyLevel
        gw_config = config.gateway
        autonomy = AutonomyLevel(gw_config.autonomy_level)
        gateway = init_gateway(
            llm_inference=llm_inference,
            autonomy=autonomy,
            max_workers=gw_config.max_workers,
            vision_enabled=vision_enabled,
        )
        await gateway.start()
        
        # Import and register skills (only needed if Gateway is running)
        from .example_skills import builtin  # noqa: F401 - imports register skills
        from . import onboarding  # Registers scan/onboard skills
        from .skills import vision_skill # noqa: F401
        from .skills import network_ops # noqa: F401 - Registers scan/deploy skills
    
    logger.info("Velvet Nadir started successfully")
    return gateway


async def stop_velvet() -> None:
    """Stop all Velvet systems."""
    try:
        gateway = get_gateway()
        await gateway.stop()
    except RuntimeError:
        pass
        
    try:
        from .scan import stop_discovery_service
        stop_discovery_service()
    except Exception:
        pass
        
    try:
        fabric = get_fabric()
        await fabric.stop()
    except RuntimeError:
        pass
        
    logger.info("Velvet Nadir stopped")


async def interactive_console() -> None:
    """
    Run an interactive console for testing.
    
    Commands:
    - wake: Simulate wake word detection
    - say <text>: Simulate speech input
    - skill <name> [args]: Execute a skill directly
    - context: Show current context
    - skills: List all skills
    - quit: Exit
    """
    try:
        import readline  # noqa: F401 - enables arrow keys in input (Unix only)
    except ImportError:
        pass  # Windows doesn't have readline
    
    # Choose real or mock audio based on config
    config = get_config()
    use_real = config.audio.use_real_audio
    
    if use_real:
        audio_monitor = AudioMonitor()
        tts_output = RealTTSOutput()
        audio_label = "REAL AUDIO"
    else:
        audio_monitor = MockAudioMonitor()
        tts_output = MockTTSOutput()
        audio_label = "MOCK AUDIO"
    
    await start_velvet()
    await audio_monitor.start()
    await tts_output.start()
    
    print("\n" + "="*60)
    print(f"* VELVET NADIR Interactive Console [{audio_label}]")
    print("="*60)
    print("Commands: wake, say <text>, skill <name>, cancel, context, skills, quit")
    print("="*60 + "\n")
    
    try:
        while True:
            try:
                # Use asyncio-friendly input
                line = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("velvet> ")
                )
            except EOFError:
                break
                
            line = line.strip()
            if not line:
                continue
                
            parts = line.split(maxsplit=1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            
            if cmd == "quit" or cmd == "exit":
                break
                
            elif cmd == "wake":
                await mock_audio.simulate_wake_word()
                
            elif cmd == "say":
                if not args:
                    print("Usage: say <text>")
                    continue
                await mock_audio.simulate_transcript(args)
                
            elif cmd == "skill":
                skill_parts = args.split(maxsplit=1)
                if not skill_parts:
                    print("Usage: skill <name> [json_params]")
                    continue
                skill_name = skill_parts[0]
                params = {}
                if len(skill_parts) > 1:
                    import json
                    try:
                        params = json.loads(skill_parts[1])
                    except json.JSONDecodeError:
                        print("Invalid JSON params")
                        continue
                
                # Route through fabric → gateway queue (not direct call)
                fabric = get_fabric()
                await fabric.publish(
                    MessageType.SKILL_REQUEST.value,
                    {"skill": skill_name, "params": params, "source": "console"},
                )
                # Give the queue a moment to process
                await asyncio.sleep(0.5)
                
            elif cmd == "cancel" or cmd == "stop":
                fabric = get_fabric()
                await fabric.publish(MessageType.CANCEL_REQUEST.value, {"source": "console"})
                print("Cancel signal sent.")
                
            elif cmd == "context":
                ctx = await get_context_manager().get_active_context()
                import json
                print(json.dumps(ctx, indent=2, default=str))
                
            elif cmd == "skills":
                skills = get_skill_registry().list_all()
                for s in skills:
                    print(f"  - {s.name}: {s.description} [{s.category.value}]")
                    
            elif cmd == "help":
                print("Commands:")
                print("  wake           - Simulate wake word detection")
                print("  say <text>     - Simulate speech input")
                print("  skill <name>   - Execute a skill")
                print("  cancel / stop  - Cancel in-progress generation")
                print("  context        - Show current context")
                print("  skills         - List all skills")
                print("  quit           - Exit")
                
            else:
                print(f"Unknown command: {cmd}. Type 'help' for commands.")
                
            # Small delay to let async handlers run
            await asyncio.sleep(0.1)
            
    finally:
        await audio_monitor.stop()
        await tts_output.stop()
        await stop_velvet()


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Velvet Nadir - Personal AI Assistant")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--config", type=Path, help="Path to config file")
    parser.add_argument("--llm", type=str, default=None, 
                        help="Enable LLM with specified model (e.g., llama3.1:8b)")
    parser.add_argument("--llm-adapter", type=str, default=None,
                        help="LLM adapter: ollama, llama.cpp, vllm (default: from config)")
    parser.add_argument("--module", action="append", default=None,
                        help="Run specific module (gateway, vision, audio, discovery). Can be repeated.")
    parser.add_argument("--connect", action="append", default=None,
                        help="Connect to Zenoh peer (e.g., tcp/192.168.1.100:7447). For Universal Nodes.")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Interactive console (text-based testing)
    subparsers.add_parser("console", help="Start interactive text console")
    
    # Live audio mode (real microphone)
    live_parser = subparsers.add_parser("live", help="Start with real audio (mic + speaker)")
    
    # Run as daemon
    run_parser = subparsers.add_parser("run", help="Start Velvet as background service")
    run_parser.add_argument("--no-audio", action="store_true", help="Disable audio monitors")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging("DEBUG" if args.debug else "INFO")
    
    # Load config
    if args.config:
        load_config(config_path=args.config)
    
    # Determine if LLM should be used
    use_llm = args.llm is not None
    llm_model = args.llm
    llm_adapter = getattr(args, 'llm_adapter', None)
    modules = args.module
    connect_peers = args.connect
    
    # Run command
    if args.command == "console" or args.command is None:
        try:
            asyncio.run(interactive_console())
        except KeyboardInterrupt:
            print("\nGoodbye!")
            
    elif args.command == "live":
        async def run_live():
            """Run with real audio pipeline."""
            # Force real audio mode
            config = get_config()
            config.audio.use_real_audio = True
            
            print("\n" + "="*60)
            print("* VELVET NADIR - Live Audio Mode")
            print("="*60)
            print(f"  LLM: {llm_model if use_llm else 'disabled'}")
            print(f"  Whisper: {config.audio.whisper_model_path or 'default'}")
            print(f"  TTS: {config.audio.tts_model_path or 'default'}")
            print(f"  Wake: {config.audio.wake_model_path or 'default'}")
            print("  Say 'Hey Velvet' to wake, or Ctrl+C to exit")
            print("="*60 + "\n")
            
            await start_velvet(use_llm=use_llm, llm_model=llm_model, llm_adapter=llm_adapter)
            
            monitor = AudioMonitor()
            tts = RealTTSOutput()
            await monitor.start()
            await tts.start()
            
            print("[MIC] Listening for wake word...")
            
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass
            finally:
                await monitor.stop()
                await tts.stop()
                await stop_velvet()
                
        try:
            asyncio.run(run_live())
        except KeyboardInterrupt:
            print("\nGoodbye!")
            
    elif args.command == "run":
        async def run():
            await start_velvet(
                use_llm=use_llm, 
                llm_model=llm_model, 
                llm_adapter=llm_adapter,
                modules=modules,
                connect_to=connect_peers
            )
            # Keep running until interrupted
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass
            finally:
                await stop_velvet()
                
        try:
            asyncio.run(run())
        except KeyboardInterrupt:
            print("\nStopping Velvet...")


if __name__ == "__main__":
    main()
