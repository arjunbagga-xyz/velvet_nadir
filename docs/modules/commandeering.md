# Hardware Commandeering Service (`services/commandeering.py`)

## Overview
`velvet.services.commandeering` allows an authorized operator to seize direct low-latency control of hardware buses (CAN bus, BLE, UART serial, CNC G-Code) and streaming modalities, bypassing typical event rate-limiters.

## Features
- **Unthrottled Stream Injection**: Switches `HardwareBusDriver` into commandeered mode, lifting default `rate_limit_sec` throttling.
- **Biometric Gate**: Commandeering dangerous peripherals (e.g. vehicle CAN bus, robot actuators) requires operator biometric authentication.
- **Auto-Release Watchdog**: Releases hardware control back to autonomous mesh governance if operator heartbeat ceases for more than 15 seconds.
