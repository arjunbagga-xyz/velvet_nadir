"""Quick test of device and model registries."""
import asyncio
from velvet.devices import (
    Device, DeviceType, HardwareRegistry,
    detect_local_hardware, detect_local_software, create_local_device
)
from velvet.models import ModelInfo, ModelType, ModelFormat, ModelRegistry

async def main():
    print("=== Testing Device Registry ===")
    
    # Test hardware detection
    hw = detect_local_hardware()
    sw = detect_local_software()
    print(f"CPU: {hw.cpu_cores} cores, RAM: {hw.ram_gb}GB")
    print(f"GPU: {hw.gpu or 'None'}")
    print(f"OS: {sw.os} {sw.os_version}")
    
    # Create local device
    device = create_local_device("test-device", "Test Machine", DeviceType.COMPUTE)
    print(f"\nLocal device: {device.name} ({device.device_type.value})")
    print(f"Capabilities: {device.capabilities}")
    
    # Test registry
    registry = HardwareRegistry()
    await registry.register(device)
    print(f"\nRegistry: {registry.get_stats()}")
    
    # Find compute devices
    compute = registry.find_compute_devices(online_only=False)
    print(f"Compute devices: {[d.name for d in compute]}")
    
    print("\n=== Testing Model Registry ===")
    
    # Create model registry
    model_reg = ModelRegistry()
    
    # Register a model
    llama = ModelInfo(
        model_id="llama-3-8b-q4",
        name="LLaMA 3 8B",
        model_type=ModelType.LLM,
        format=ModelFormat.GGUF,
        size_gb=4.5,
        capabilities=["chat", "code"],
        context_length=8192,
        quantization="q4_k_m",
    )
    
    await model_reg.register_model("test-device", llama)
    print(f"Registered model: {llama.name}")
    
    # Find models
    devices = model_reg.get_model_devices("llama-3-8b-q4")
    print(f"Model on devices: {devices}")
    
    print(f"\nModel registry stats: {model_reg.get_stats()}")
    
    print("\n=== All tests passed! ===")

if __name__ == "__main__":
    asyncio.run(main())
