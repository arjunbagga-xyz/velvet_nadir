# Hardware Drivers Subsystem (`drivers.py`, `drivers/bus.py`)

## Overview
Provides modular abstractions for interfacing with hardware peripherals, sensors, robotics, and industrial buses across the mesh.

## Components
- `DeviceDriver`: Abstract base class specifying `connect()`, `disconnect()`, `get_status()`, and event publishing.
- `CANBusDriver`: Dual DBC frame decoding and raw hex streaming for automotive CAN networks.
- `BLEBusDriver`: Bluetooth Low Energy peripheral scanning and GATT characteristic notifications.
- `SerialBusDriver`: High-speed UART streaming for microcontrollers and embedded sensors.
- `CNCGCodeDriver`: G-Code streaming and Moonraker/OctoPrint REST integration for 3D printers and CNC mills.
