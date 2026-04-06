import asyncio
from velvet.config import get_config
from velvet.devices import init_registry, get_registry, create_local_device, DeviceType
from velvet.llm import MeshLLMAdapter
from velvet.fabric import init_fabric

async def test():
    config = get_config()
    await init_fabric(device_id=config.device_id, mode="local")
    registry = await init_registry(with_fabric=True)
    dev = create_local_device(device_id=config.device_id, name='Host', device_type=DeviceType.COMPUTE)
    await registry.register(dev)
    registry.start_heartbeat(dev.device_id)
    
    # Simulate LLMProvider updating capabilities
    my_device = registry.get_device(config.device_id)
    if my_device and "llm" not in my_device.capabilities:
        my_device.capabilities.append("llm")
        await registry.register(my_device)
        
    # Wait to let fabric subscribers process and the cleanup loop run once
    await asyncio.sleep(15)
    
    print('Online BEFORE:', len(get_registry().get_online_devices()))
    
    adapter = MeshLLMAdapter()
    best = adapter._select_best_node()
    print('Best node:', best.device_id if best else None)

asyncio.run(test())
