export type Device = {
  id: string;
  name: string;
  type: 'compute' | 'sensor' | 'hybrid' | 'output';
  status: 'online' | 'degraded' | 'offline';
  load: number;
  battery?: number;
  models: string[];
  capabilities: string[];
  location: [number, number];
  peripherals: { name: string; status: 'active' | 'inactive' | 'error' }[];
  files: { name: string; size: string; type: 'folder' | 'file' }[];
  x?: number;
  y?: number;
};

export type ContextEntity = {
  name: string;
  task: string;
  status: 'active' | 'idle' | 'waiting';
};

export type ContextInstance = {
  id: string;
  name: string;
  type: 'personal' | 'workshop' | 'hedgefund' | 'maintenance';
  status: 'active' | 'monitoring' | 'idle';
  progress: number;
  agents: ContextEntity[];
  humans: ContextEntity[];
  robots: ContextEntity[];
  hardware: ContextEntity[];
  artifacts: string[];
  x: number;
  y: number;
};

export type StreamEvent = {
  id: string;
  timestamp: string;
  source: string;
  type: 'audio' | 'video' | 'gps' | 'system';
  content: string;
  level: 'info' | 'wake' | 'reasoning';
};

export const INITIAL_DEVICES: Device[] = [
  { 
    id: 'dev_1', name: 'Jetson Thor', type: 'compute', status: 'online', load: 45, battery: 82, 
    models: ['LLaMA-70B', 'Whisper-Large'], capabilities: ['Heavy Compute', 'Reasoning', 'Vision'], location: [37.7749, -122.4194],
    peripherals: [{ name: 'WiFi 6E', status: 'active' }, { name: 'Bluetooth 5.3', status: 'active' }, { name: 'NVMe SSD', status: 'active' }],
    files: [{ name: 'models', size: '--', type: 'folder' }, { name: 'context_db.sqlite', size: '2.4 GB', type: 'file' }, { name: 'system.log', size: '12 MB', type: 'file' }],
    x: 600, y: 300
  },
  { 
    id: 'dev_2', name: 'Smart Glasses', type: 'hybrid', status: 'online', load: 12, battery: 64, 
    models: ['TinyML-VAD'], capabilities: ['Display', 'Audio In/Out', 'Camera'], location: [37.7749, -122.4194],
    peripherals: [{ name: 'RGB Camera', status: 'active' }, { name: 'Bone Conduction Mic', status: 'active' }, { name: 'Micro-OLED', status: 'active' }],
    files: [{ name: 'recordings', size: '--', type: 'folder' }, { name: 'cache.tmp', size: '45 MB', type: 'file' }],
    x: 400, y: 400
  },
  { 
    id: 'dev_3', name: 'Workshop Cam', type: 'sensor', status: 'online', load: 5, 
    models: ['YOLOv8-Nano'], capabilities: ['Video Stream', 'Motion Detect'], location: [37.7812, -122.4051],
    peripherals: [{ name: '4K Sensor', status: 'active' }, { name: 'IR Illuminator', status: 'inactive' }],
    files: [{ name: 'timelapse', size: '--', type: 'folder' }],
    x: 800, y: 400
  },
  { 
    id: 'dev_4', name: 'GPU Cluster', type: 'compute', status: 'degraded', load: 92, 
    models: ['Stable Diffusion', 'Custom-Quant'], capabilities: ['Training', 'Parallel Inference'], location: [40.7128, -74.0060],
    peripherals: [{ name: '100G NIC', status: 'active' }, { name: 'Cooling Array', status: 'error' }],
    files: [{ name: 'training_data', size: '--', type: 'folder' }, { name: 'weights.pt', size: '14 GB', type: 'file' }],
    x: 800, y: 600
  },
  { 
    id: 'dev_5', name: 'Phone', type: 'hybrid', status: 'online', load: 28, battery: 41, 
    models: ['Whisper-Small', 'Gemini-Nano'], capabilities: ['Fallback Brain', 'GPS', 'Mic'], location: [37.7749, -122.4194],
    peripherals: [{ name: 'GPS', status: 'active' }, { name: 'Mic Array', status: 'active' }, { name: '5G Modem', status: 'active' }],
    files: [{ name: 'offline_maps', size: '--', type: 'folder' }, { name: 'sync_queue.db', size: '1.2 MB', type: 'file' }],
    x: 400, y: 600
  },
  { 
    id: 'dev_6', name: 'HVAC Sensors', type: 'sensor', status: 'online', load: 2, battery: 98, 
    models: ['TinyML-Anomaly'], capabilities: ['Temperature', 'Humidity', 'Air Quality'], location: [37.7749, -122.4194],
    peripherals: [{ name: 'Temp Sensor', status: 'active' }, { name: 'Air Quality', status: 'active' }],
    files: [{ name: 'logs', size: '--', type: 'folder' }],
    x: 400, y: 700
  },
];

export const INITIAL_CONTEXTS: ContextInstance[] = [
  { 
    id: 'ctx_1', name: 'Personal Context', type: 'personal', status: 'active', progress: 100, x: 200, y: 200,
    agents: [{ name: 'Velvet-Core', task: 'Orchestrating daily schedule', status: 'active' }, { name: 'Schedule-Opt', task: 'Finding meeting slots', status: 'idle' }], 
    humans: [{ name: 'Me', task: 'Reviewing emails', status: 'active' }], 
    robots: [], 
    hardware: [{ name: 'Smart Glasses', task: 'Displaying notifications', status: 'active' }, { name: 'Phone', task: 'Location tracking', status: 'active' }], 
    artifacts: ['Daily Briefing', 'Health Stats']
  },
  { 
    id: 'ctx_2', name: 'Workshop Context', type: 'workshop', status: 'monitoring', progress: 45, x: 1000, y: 200,
    agents: [{ name: 'CAD-Gen', task: 'Generating motor mounts', status: 'active' }, { name: 'Safety-Monitor', task: 'Watching tool usage', status: 'active' }], 
    humans: [{ name: 'Me', task: 'Soldering wires', status: 'active' }], 
    robots: [{ name: 'Arm-1', task: 'Holding PCB', status: 'idle' }, { name: 'CNC-Router', task: 'Cutting carbon fiber', status: 'active' }], 
    hardware: [{ name: 'Workshop Cam', task: 'Streaming 4K', status: 'active' }, { name: 'Jetson Thor', task: 'Running YOLOv8', status: 'active' }], 
    artifacts: ['Drone Frame v2 CAD', 'Material BOM']
  },
  { 
    id: 'ctx_3', name: 'Autonomous Hedgefund', type: 'hedgefund', status: 'active', progress: 82, x: 1000, y: 600,
    agents: [{ name: 'Quant-Alpha', task: 'Backtesting strategy', status: 'active' }, { name: 'Risk-Manager', task: 'Calculating VaR', status: 'active' }], 
    humans: [], 
    robots: [], 
    hardware: [{ name: 'GPU Cluster', task: 'Training models', status: 'active' }], 
    artifacts: ['Daily P&L', 'Position Sizing Report']
  },
  { 
    id: 'ctx_4', name: 'Facility Maintenance', type: 'maintenance', status: 'idle', progress: 15, x: 200, y: 600,
    agents: [{ name: 'Predictive-Maint', task: 'Analyzing HVAC logs', status: 'active' }], 
    humans: [{ name: 'Tech-Dave', task: 'En route to site', status: 'waiting' }], 
    robots: [{ name: 'Drone-Inspector', task: 'Charging', status: 'idle' }], 
    hardware: [{ name: 'HVAC Sensors', task: 'Logging temp', status: 'active' }], 
    artifacts: ['Maintenance Log', 'Parts Order']
  },
];

export const INITIAL_EVENTS: StreamEvent[] = [
  { id: 'ev_1', timestamp: '10:42:01', source: 'Smart Glasses', type: 'video', content: 'User focused on monitor', level: 'info' },
  { id: 'ev_2', timestamp: '10:42:15', source: 'Phone Mic', type: 'audio', content: 'Speech detected: "Hey Velvet, what\'s next?"', level: 'wake' },
  { id: 'ev_3', timestamp: '10:42:16', source: 'Jetson Thor', type: 'system', content: 'Intent parsed: Schedule query', level: 'reasoning' },
  { id: 'ev_4', timestamp: '10:42:18', source: 'GPU Cluster', type: 'system', content: 'LLM Response generated (1.2s)', level: 'info' },
];

export const MEMORY_NODES = [
  // Tier 1: Contexts
  { id: 'Personal Context', tier: 1, type: 'context' },
  { id: 'Workshop Context', tier: 1, type: 'context' },
  { id: 'Hedgefund Context', tier: 1, type: 'context' },
  
  // Tier 2: Agents & Systems
  { id: 'Velvet-Core', tier: 2, type: 'agent' },
  { id: 'CAD-Gen', tier: 2, type: 'agent' },
  { id: 'Quant-Alpha', tier: 2, type: 'agent' },
  { id: 'Context Manager', tier: 2, type: 'system' },
  
  // Tier 3: Entities & Data
  { id: 'Sarah', tier: 3, type: 'person' },
  { id: 'Drone Frame v2', tier: 3, type: 'project' },
  { id: 'Carbon Fiber', tier: 3, type: 'material' },
  { id: 'NVIDIA', tier: 3, type: 'asset' },
  { id: 'Meeting 3PM', tier: 3, type: 'event' },
];

export const MEMORY_LINKS = [
  { source: 'Personal Context', target: 'Velvet-Core', value: 2, label: 'managed_by' },
  { source: 'Personal Context', target: 'Context Manager', value: 1, label: 'syncs_to' },
  { source: 'Workshop Context', target: 'CAD-Gen', value: 2, label: 'managed_by' },
  { source: 'Hedgefund Context', target: 'Quant-Alpha', value: 2, label: 'managed_by' },
  
  { source: 'Velvet-Core', target: 'Sarah', value: 1, label: 'knows' },
  { source: 'Velvet-Core', target: 'Meeting 3PM', value: 1, label: 'schedules' },
  { source: 'CAD-Gen', target: 'Drone Frame v2', value: 3, label: 'designs' },
  { source: 'Drone Frame v2', target: 'Carbon Fiber', value: 2, label: 'uses' },
  { source: 'Quant-Alpha', target: 'NVIDIA', value: 3, label: 'trades' },
];
