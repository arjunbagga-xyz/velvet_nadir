# 🔌 Extensibility Architecture

> How Velvet Nadir grows and adapts with new capabilities

---

## 📐 Design Philosophy

Velvet Nadir is designed to be **infinitely extensible** without requiring core system changes. The extension architecture follows these principles:

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          EXTENSIBILITY PRINCIPLES                                   │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   1. PLUG-AND-PLAY                                                                 │
│      └─ New devices and capabilities should "just work" when connected             │
│                                                                                     │
│   2. HOT-SWAPPABLE                                                                 │
│      └─ Extensions can be added/removed at runtime without restart                 │
│                                                                                     │
│   3. ISOLATED                                                                      │
│      └─ Extension failures don't crash the core system                             │
│                                                                                     │
│   4. DISCOVERABLE                                                                  │
│      └─ System automatically discovers and registers new extensions                │
│                                                                                     │
│   5. COMPOSABLE                                                                    │
│      └─ Extensions can use other extensions' capabilities                          │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🧩 Extension Types

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              EXTENSION TYPES                                        │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │  TYPE: DEVICE DRIVER                                                        │  │
│   │  ════════════════════                                                       │  │
│   │  Purpose: Connect new hardware to the mesh                                  │  │
│   │                                                                             │  │
│   │  Examples:                                                                  │  │
│   │  • USB Camera driver                                                        │  │
│   │  • Bluetooth microphone driver                                              │  │
│   │  • GPS module driver                                                        │  │
│   │  • LiDAR sensor driver                                                      │  │
│   │  • Smart home hub bridge                                                    │  │
│   │                                                                             │  │
│   │  Provides: Raw sensor data → Mesh                                           │  │
│   │  Interface: DeviceDriver                                                    │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │  TYPE: STREAM PROCESSOR                                                     │  │
│   │  ═════════════════════                                                      │  │
│   │  Purpose: Process sensor data into structured events                        │  │
│   │                                                                             │  │
│   │  Examples:                                                                  │  │
│   │  • Speech-to-Text processor                                                 │  │
│   │  • Object detection processor                                               │  │
│   │  • Face recognition processor                                               │  │
│   │  • Gesture recognition processor                                            │  │
│   │  • Emotion detection processor                                              │  │
│   │                                                                             │  │
│   │  Provides: Raw data → Structured events                                     │  │
│   │  Interface: StreamProcessor                                                 │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │  TYPE: CAPABILITY                                                           │  │
│   │  ════════════════                                                           │  │
│   │  Purpose: Add new AI-powered abilities                                      │  │
│   │                                                                             │  │
│   │  Examples:                                                                  │  │
│   │  • CAD Model Generator                                                      │  │
│   │  • Video Editor                                                             │  │
│   │  • Music Composer                                                           │  │
│   │  • Code Generator                                                           │  │
│   │  • Document Analyzer                                                        │  │
│   │                                                                             │  │
│   │  Provides: Agent-callable tools                                             │  │
│   │  Interface: Capability                                                      │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │  TYPE: INTEGRATION                                                          │  │
│   │  ══════════════════                                                         │  │
│   │  Purpose: Connect to external services and data sources                     │  │
│   │                                                                             │  │
│   │  Examples:                                                                  │  │
│   │  • Calendar sync (Google/Outlook)                                           │  │
│   │  • Email integration                                                        │  │
│   │  • CRM connector                                                            │  │
│   │  • Accounting software bridge                                               │  │
│   │  • Smart home (HomeAssistant/HomeKit)                                       │  │
│   │  • Project management (Jira/Linear)                                         │  │
│   │                                                                             │  │
│   │  Provides: Bidirectional data sync                                          │  │
│   │  Interface: Integration                                                     │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │  TYPE: OUTPUT ADAPTER                                                       │  │
│   │  ═══════════════════                                                        │  │
│   │  Purpose: Send outputs to new device types                                  │  │
│   │                                                                             │  │
│   │  Examples:                                                                  │  │
│   │  • Smart glasses display                                                    │  │
│   │  • E-ink display                                                            │  │
│   │  • Projector control                                                        │  │
│   │  • Robot arm movement                                                       │  │
│   │  • 3D printer commands                                                      │  │
│   │                                                                             │  │
│   │  Provides: Action commands → Physical device                                │  │
│   │  Interface: OutputAdapter                                                   │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │  TYPE: CONTEXT PROVIDER                                                     │  │
│   │  ═════════════════════                                                      │  │
│   │  Purpose: Create new context instances for specific domains                 │  │
│   │                                                                             │  │
│   │  Examples:                                                                  │  │
│   │  • Business Operations Context                                              │  │
│   │  • Health & Fitness Context                                                 │  │
│   │  • Vehicle Context                                                          │  │
│   │  • Kitchen/Cooking Context                                                  │  │
│   │                                                                             │  │
│   │  Provides: Domain-specific awareness                                        │  │
│   │  Interface: ContextProvider                                                 │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📋 Extension Interface Specifications

### Base Extension Interface

```typescript
// All extensions implement this base interface
interface VelvetExtension {
  // Identity
  id: string;                    // Unique identifier
  name: string;                  // Human-readable name
  version: string;               // Semantic version
  type: ExtensionType;           // device | processor | capability | integration | output | context
  
  // Metadata
  description: string;           // What this extension does
  author: string;                // Creator
  dependencies: string[];        // Other extensions required
  
  // Lifecycle
  onLoad(): Promise<void>;       // Called when extension is loaded
  onUnload(): Promise<void>;     // Called before unloading
  onHealthCheck(): Promise<HealthStatus>;  // Periodic health check
  
  // Configuration
  getConfig(): ExtensionConfig;
  setConfig(config: ExtensionConfig): Promise<void>;
}
```

### Device Driver Interface

```typescript
interface DeviceDriver extends VelvetExtension {
  type: "device";
  
  // Device capabilities
  sensorTypes: SensorType[];     // What sensors this device provides
  outputTypes: OutputType[];     // What outputs it can produce
  
  // Connection
  connect(): Promise<void>;
  disconnect(): Promise<void>;
  getConnectionStatus(): ConnectionStatus;
  
  // Data streaming
  startStream(sensor: SensorType): Promise<StreamHandle>;
  stopStream(handle: StreamHandle): Promise<void>;
  
  // Events
  onData: EventEmitter<SensorData>;
  onError: EventEmitter<DeviceError>;
}
```

### Capability Interface

```typescript
interface Capability extends VelvetExtension {
  type: "capability";
  
  // What this capability can do
  tools: ToolDefinition[];       // Tools exposed to agents
  
  // Execution
  execute(tool: string, params: any): Promise<ToolResult>;
  
  // Resource requirements
  computeRequirements: {
    minRAM: number;              // MB
    preferGPU: boolean;
    modelSize?: number;          // MB, if uses local model
  };
}

// Tool definition (similar to function calling)
interface ToolDefinition {
  name: string;
  description: string;
  parameters: JSONSchema;
  returns: JSONSchema;
  examples: Example[];
}
```

### Integration Interface

```typescript
interface Integration extends VelvetExtension {
  type: "integration";
  
  // Authentication
  authenticate(credentials: Credentials): Promise<void>;
  isAuthenticated(): boolean;
  
  // Data sync
  sync(): Promise<SyncResult>;
  getSyncStatus(): SyncStatus;
  
  // Real-time updates
  subscribe(events: string[]): Promise<void>;
  onUpdate: EventEmitter<IntegrationUpdate>;
  
  // Actions
  sendAction(action: IntegrationAction): Promise<ActionResult>;
}
```

---

## 📁 Extension Package Structure

```
my-extension/
├── manifest.yaml           # Extension metadata
├── extension.py            # Main extension code (or .ts, .js)
├── config.schema.json      # Configuration schema
├── README.md               # Documentation
├── requirements.txt        # Python dependencies (if Python)
├── package.json            # Node dependencies (if JS/TS)
├── models/                 # Local models (if any)
│   └── model.onnx
├── assets/                 # Static assets
│   ├── icon.png
│   └── ui_components/
└── tests/                  # Extension tests
    └── test_extension.py
```

### Manifest Example

```yaml
# manifest.yaml
id: "velvet.capability.cad-generator"
name: "CAD Model Generator"
version: "1.0.0"
type: "capability"

description: "Generate 3D CAD models from text descriptions"
author: "Your Name"
license: "MIT"

# Dependencies
dependencies:
  - "velvet.core >= 1.0.0"    # Core system version
  
optionalDependencies:
  - "velvet.integration.fusion360"  # Enhanced if available

# Runtime requirements
requirements:
  minRAM: 2048                # MB
  preferGPU: true
  platforms:
    - "linux"
    - "windows"

# Configuration
config:
  schema: "./config.schema.json"
  defaults:
    model_quality: "balanced"
    max_iterations: 5

# Entry point
entrypoint: "extension.py"
class: "CADGeneratorCapability"

# Tools exposed
tools:
  - name: "generate_cad"
    description: "Generate a 3D model from description"
  - name: "modify_cad"
    description: "Modify an existing 3D model"
  - name: "export_cad"
    description: "Export model to various formats"
```

---

## 🔄 Extension Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            EXTENSION LIFECYCLE                                      │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   INSTALLATION                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │  1. User adds extension (copy folder, or install from registry)            │  │
│   │  2. System reads manifest.yaml                                              │  │
│   │  3. Validates dependencies and requirements                                 │  │
│   │  4. Installs package dependencies                                           │  │
│   │  5. Registers extension in system catalog                                   │  │
│   │  6. Status: INSTALLED                                                       │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                              │
│                                      ▼                                              │
│   LOADING                                                                          │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │  1. System imports extension module                                         │  │
│   │  2. Creates extension instance                                              │  │
│   │  3. Calls onLoad()                                                          │  │
│   │  4. Extension registers its tools/capabilities                              │  │
│   │  5. Status: LOADED                                                          │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                              │
│                                      ▼                                              │
│   ACTIVE                                                                           │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │  • Extension is available for use                                           │  │
│   │  • Responds to tool calls                                                   │  │
│   │  • Receives relevant events                                                 │  │
│   │  • Periodic health checks                                                   │  │
│   │  • Status: ACTIVE                                                           │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                              │
│                              ┌───────┴───────┐                                      │
│                              ▼               ▼                                      │
│   PAUSE/RESUME                         UNLOAD                                      │
│   ┌──────────────────┐                 ┌──────────────────┐                        │
│   │  • Temporarily   │                 │  1. Calls        │                        │
│   │    disabled      │                 │     onUnload()   │                        │
│   │  • Keeps state   │                 │  2. Cleans up    │                        │
│   │  • Quick resume  │                 │     resources    │                        │
│   │  • Status:       │                 │  3. Unregisters  │                        │
│   │    PAUSED        │                 │     from catalog │                        │
│   └──────────────────┘                 │  4. Status:      │                        │
│                                        │     UNLOADED     │                        │
│                                        └──────────────────┘                        │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔍 Extension Discovery & Registry

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          EXTENSION DISCOVERY                                        │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   LOCAL DISCOVERY:                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                             │  │
│   │   velvet/                                                                   │  │
│   │   └── extensions/                                                           │  │
│   │       ├── installed/              # User-installed extensions               │  │
│   │       │   ├── cad-generator/                                                │  │
│   │       │   └── home-assistant/                                               │  │
│   │       ├── builtin/                # Core extensions                         │  │
│   │       │   ├── speech-to-text/                                               │  │
│   │       │   └── face-recognition/                                             │  │
│   │       └── dev/                    # Development extensions                  │  │
│   │           └── my-new-extension/                                             │  │
│   │                                                                             │  │
│   │   System watches these directories for changes                              │  │
│   │   New folders = new extensions to register                                  │  │
│   │                                                                             │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│   EXTENSION REGISTRY (Internal Catalog):                                          │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                             │  │
│   │  {                                                                          │  │
│   │    "velvet.capability.cad-generator": {                                     │  │
│   │      "version": "1.0.0",                                                    │  │
│   │      "status": "ACTIVE",                                                    │  │
│   │      "path": "/extensions/installed/cad-generator",                         │  │
│   │      "tools": ["generate_cad", "modify_cad", "export_cad"],                 │  │
│   │      "loadedAt": "2026-02-01T10:00:00Z",                                    │  │
│   │      "health": "OK",                                                        │  │
│   │      "lastHealthCheck": "2026-02-01T16:30:00Z"                              │  │
│   │    },                                                                       │  │
│   │    "velvet.device.usb-camera": {                                            │  │
│   │      "version": "1.2.0",                                                    │  │
│   │      "status": "ACTIVE",                                                    │  │
│   │      "sensors": ["video"],                                                  │  │
│   │      "health": "OK"                                                         │  │
│   │    }                                                                        │  │
│   │  }                                                                          │  │
│   │                                                                             │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🤖 Agent Tool Discovery

When extensions are loaded, their tools become available to the reasoning engine:

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                       AGENT TOOL DISCOVERY                                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   AVAILABLE TOOLS (auto-generated from extensions):                                │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                             │  │
│   │  tools:                                                                     │  │
│   │    # From core                                                              │  │
│   │    - name: "get_context"                                                    │  │
│   │      description: "Get current context state"                               │  │
│   │      source: "velvet.core.context"                                          │  │
│   │                                                                             │  │
│   │    - name: "search_memory"                                                  │  │
│   │      description: "Search past events and knowledge"                        │  │
│   │      source: "velvet.core.memory"                                           │  │
│   │                                                                             │  │
│   │    # From extensions                                                        │  │
│   │    - name: "generate_cad"                                                   │  │
│   │      description: "Generate a 3D model from text"                           │  │
│   │      source: "velvet.capability.cad-generator"                              │  │
│   │      parameters:                                                            │  │
│   │        description: string (required)                                       │  │
│   │        style: "mechanical" | "organic" (optional)                           │  │
│   │                                                                             │  │
│   │    - name: "control_lights"                                                 │  │
│   │      description: "Control smart home lighting"                             │  │
│   │      source: "velvet.integration.home-assistant"                            │  │
│   │      parameters:                                                            │  │
│   │        room: string                                                         │  │
│   │        state: "on" | "off" | brightness (0-100)                             │  │
│   │                                                                             │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│   TOOL ROUTING:                                                                    │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                             │  │
│   │  User: "Design a bracket to hold the sensor"                                │  │
│   │                                                                             │  │
│   │  Agent reasoning:                                                           │  │
│   │  1. This is a CAD design request                                           │  │
│   │  2. Check available tools → "generate_cad" available                        │  │
│   │  3. Call: generate_cad(description="bracket for sensor mounting")           │  │
│   │                                                                             │  │
│   │  Tool Router:                                                               │  │
│   │  1. Look up "generate_cad" → source: "velvet.capability.cad-generator"      │  │
│   │  2. Route to CAD Generator extension                                        │  │
│   │  3. Extension executes, returns result                                      │  │
│   │  4. Return to agent                                                         │  │
│   │                                                                             │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔒 Extension Sandboxing

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          EXTENSION SECURITY                                         │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   PERMISSION MODEL:                                                                │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                             │  │
│   │  # Declared in manifest.yaml                                                │  │
│   │  permissions:                                                               │  │
│   │    - "sensor.audio"         # Can access audio streams                      │  │
│   │    - "sensor.video"         # Can access video streams                      │  │
│   │    - "context.read"         # Can read context state                        │  │
│   │    - "context.write"        # Can modify context (rare)                     │  │
│   │    - "memory.read"          # Can search memories                           │  │
│   │    - "memory.write"         # Can create memories (rare)                    │  │
│   │    - "network.local"        # Can access local network                      │  │
│   │    - "network.internet"     # Can access internet (requires approval)       │  │
│   │    - "filesystem.read"      # Can read files                                │  │
│   │    - "filesystem.write"     # Can write files (sandboxed)                   │  │
│   │                                                                             │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│   SANDBOXING:                                                                      │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                             │  │
│   │  Extension runs in isolated environment:                                    │  │
│   │  • Separate process (crash isolation)                                       │  │
│   │  • Limited filesystem (only extension folder + data folder)                 │  │
│   │  • Network filtered through proxy                                           │  │
│   │  • Resource limits (CPU, memory, disk)                                      │  │
│   │  • Timeout enforcement                                                      │  │
│   │                                                                             │  │
│   │  Communication via IPC (gRPC / message passing)                             │  │
│   │                                                                             │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│   APPROVAL FLOW:                                                                   │
│   ┌─────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                             │  │
│   │  1. Extension requests permission at install                                │  │
│   │  2. System shows user what permissions are needed                           │  │
│   │  3. User approves or denies                                                 │  │
│   │  4. Extension runs with granted permissions only                            │  │
│   │  5. Permission violations logged and blocked                                │  │
│   │                                                                             │  │
│   └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Example Extensions

### Example 1: CAD Generator Capability

```python
# cad_generator/extension.py

from velvet import Capability, ToolResult

class CADGeneratorCapability(Capability):
    """Generate 3D CAD models from text descriptions."""
    
    id = "velvet.capability.cad-generator"
    name = "CAD Model Generator"
    version = "1.0.0"
    
    tools = [
        {
            "name": "generate_cad",
            "description": "Generate a 3D model from a text description",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Natural language description of the model"
                    },
                    "style": {
                        "type": "string",
                        "enum": ["mechanical", "organic", "architectural"],
                        "default": "mechanical"
                    }
                },
                "required": ["description"]
            }
        }
    ]
    
    async def on_load(self):
        # Load the CAD generation model
        self.model = await self.load_model("models/cad_gen.onnx")
    
    async def execute(self, tool: str, params: dict) -> ToolResult:
        if tool == "generate_cad":
            # Generate the model
            mesh = await self.model.generate(
                prompt=params["description"],
                style=params.get("style", "mechanical")
            )
            
            # Save to temp file
            output_path = self.save_mesh(mesh, format="step")
            
            return ToolResult(
                success=True,
                data={
                    "file_path": output_path,
                    "format": "STEP",
                    "preview_image": self.render_preview(mesh)
                }
            )
```

### Example 2: Home Assistant Integration

```python
# home_assistant/extension.py

from velvet import Integration, IntegrationUpdate

class HomeAssistantIntegration(Integration):
    """Connect to Home Assistant for smart home control."""
    
    id = "velvet.integration.home-assistant"
    name = "Home Assistant"
    version = "1.0.0"
    
    tools = [
        {
            "name": "control_device",
            "description": "Control a smart home device",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string"},
                    "action": {"type": "string"},
                    "params": {"type": "object"}
                }
            }
        },
        {
            "name": "get_device_state",
            "description": "Get current state of a device",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string"}
                }
            }
        }
    ]
    
    async def authenticate(self, credentials):
        self.client = HomeAssistantClient(
            url=credentials["url"],
            token=credentials["token"]
        )
        await self.client.connect()
    
    async def subscribe(self, events):
        # Subscribe to state changes
        async for event in self.client.subscribe_events():
            await self.emit_update(IntegrationUpdate(
                type="state_change",
                data=event
            ))
    
    async def execute(self, tool: str, params: dict):
        if tool == "control_device":
            return await self.client.call_service(
                entity_id=params["entity_id"],
                action=params["action"],
                **params.get("params", {})
            )
```

---

## 📈 Roadmap: Planned Extensions

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          EXTENSION ROADMAP                                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   PHASE 1 (Core)           PHASE 2 (Expansion)       PHASE 3 (Advanced)           │
│   ─────────────            ───────────────────       ──────────────────            │
│                                                                                     │
│   ☐ Speech-to-Text         ☐ CAD Generator           ☐ Robot Arm Control          │
│   ☐ Object Detection       ☐ Video Editor            ☐ CNC/3D Printer             │
│   ☐ Face Recognition       ☐ Music Generator         ☐ Vehicle Integration        │
│   ☐ Basic Display          ☐ Calendar Sync           ☐ AR/VR Displays             │
│   ☐ Audio Output           ☐ Email Integration       ☐ Manufacturing              │
│   ☐ GPS Location           ☐ Home Assistant          ☐ Business Operations        │
│                            ☐ Project Management      ☐ Custom Models              │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

*The extension system is the future-proofing mechanism. Whatever capabilities you need tomorrow, you can build today.*
