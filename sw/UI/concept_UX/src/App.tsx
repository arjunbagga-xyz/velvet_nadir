import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import { 
  Activity, Cpu, Network, Database, Settings, 
  Mic, Video, MapPin, Brain, Zap,
  CheckCircle2, Shield,
  Terminal, Layers, Globe, Radio, Server, Smartphone,
  Glasses, Camera, Menu, X, Plus, Search, Users, Wrench, FileText, Bot
} from 'lucide-react';
import AgentOrb from './components/AgentOrb';
import MemoryGraph from './components/MemoryGraph';
import { 
  Device, ContextInstance, StreamEvent, 
  INITIAL_DEVICES, INITIAL_CONTEXTS, INITIAL_EVENTS 
} from './data';

const DeviceIcon = ({ type, name }: { type: string, name: string }) => {
  if (name.includes('Glasses')) return <Glasses size={18} />;
  if (name.includes('Phone')) return <Smartphone size={18} />;
  if (name.includes('Cam')) return <Camera size={18} />;
  if (name.includes('Cluster')) return <Server size={18} />;
  return <Cpu size={18} />;
};

const EventIcon = ({ type }: { type: string }) => {
  switch (type) {
    case 'audio': return <Mic size={14} className="text-blue-400" />;
    case 'video': return <Video size={14} className="text-purple-400" />;
    case 'gps': return <MapPin size={14} className="text-emerald-400" />;
    default: return <Activity size={14} className="text-gray-400" />;
  }
};

export default function App() {
  const [currentView, setCurrentView] = useState('mesh');
  const [selectedContext, setSelectedContext] = useState<ContextInstance | null>(null);
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);
  
  const [events, setEvents] = useState<StreamEvent[]>(INITIAL_EVENTS);
  const [devices, setDevices] = useState<Device[]>(INITIAL_DEVICES);
  const [contexts] = useState<ContextInstance[]>(INITIAL_CONTEXTS);
  const eventsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (currentView === 'logs') {
      eventsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [events, currentView]);

  useEffect(() => {
    const interval = setInterval(() => {
      const newEvent: StreamEvent = {
        id: `ev_${Date.now()}`,
        timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
        source: ['Smart Glasses', 'Phone Mic', 'Workshop Cam', 'GPS Module'][Math.floor(Math.random() * 4)],
        type: ['audio', 'video', 'gps', 'system'][Math.floor(Math.random() * 4)] as any,
        content: ['Motion detected in peripheral', 'Background noise: typing', 'Location stable', 'Heart rate: 72bpm'][Math.floor(Math.random() * 4)],
        level: Math.random() > 0.8 ? 'wake' : 'info'
      };
      setEvents(prev => [...prev.slice(-49), newEvent]);
      
      setDevices(prev => prev.map(d => ({
        ...d,
        load: Math.max(0, Math.min(100, d.load + (Math.random() * 10 - 5)))
      })));
    }, 3500);
    return () => clearInterval(interval);
  }, []);

  const NavItem = ({ icon: Icon, label, id }: { icon: any, label: string, id: string }) => {
    const active = currentView === id;
    return (
      <button 
        onClick={() => setCurrentView(id)}
        className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors touch-manipulation whitespace-nowrap ${active ? 'bg-surface-hover text-accent' : 'text-text-secondary hover:text-text-primary hover:bg-surface-hover/50'}`}
      >
        <Icon size={18} />
        <span className="font-medium text-sm hidden md:inline-block">{label}</span>
      </button>
    );
  };

  const renderView = () => {
    switch (currentView) {
      case 'mesh':
        return (
          <div className="relative w-full h-[calc(100vh-8rem)] bg-bg border border-border rounded-xl overflow-hidden">
            <TransformWrapper
              initialScale={1}
              initialPositionX={0}
              initialPositionY={0}
              minScale={0.5}
              maxScale={3}
              centerOnInit
            >
              <TransformComponent wrapperClass="w-full h-full cursor-grab active:cursor-grabbing">
                <div className="w-[1200px] h-[800px] relative bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.05)_1px,transparent_1px)] bg-[length:20px_20px]">
                  
                  {/* Draw connecting lines (mock mesh) */}
                  <svg className="absolute inset-0 w-full h-full pointer-events-none z-0">
                    {/* Context to Device connections */}
                    {contexts.map(ctx => 
                      ctx.hardware.map(hw => {
                        const device = devices.find(d => d.name === hw.name);
                        if (!device) return null;
                        return (
                          <line 
                            key={`${ctx.id}-${device.id}`}
                            x1={ctx.x} 
                            y1={ctx.y} 
                            x2={device.x} 
                            y2={device.y} 
                            stroke="rgba(242,125,38,0.2)" 
                            strokeWidth="2" 
                            strokeDasharray="4 4" 
                          />
                        );
                      })
                    )}
                    
                    {/* Device to Device connections */}
                    {[
                      ['Jetson Thor', 'GPU Cluster'],
                      ['Phone', 'Smart Glasses'],
                      ['Jetson Thor', 'Workshop Cam']
                    ].map(([name1, name2]) => {
                      const d1 = devices.find(d => d.name === name1);
                      const d2 = devices.find(d => d.name === name2);
                      if (!d1 || !d2) return null;
                      return (
                        <line 
                          key={`${d1.id}-${d2.id}`}
                          x1={d1.x} 
                          y1={d1.y} 
                          x2={d2.x} 
                          y2={d2.y} 
                          stroke="rgba(255,255,255,0.1)" 
                          strokeWidth="2" 
                        />
                      );
                    })}
                  </svg>

                  {/* Render Contexts */}
                  {contexts.map(ctx => (
                    <motion.div
                      key={ctx.id}
                      className={`absolute w-64 p-4 rounded-xl border-2 shadow-2xl cursor-pointer transition-colors ${
                        selectedContext?.id === ctx.id 
                          ? 'border-accent bg-surface z-20 shadow-accent/20' 
                          : 'border-border bg-surface/80 hover:border-accent/50 z-10'
                      }`}
                      style={{ left: ctx.x - 128, top: ctx.y - 60 }} // Center the card
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedDevice(null);
                        setSelectedContext(ctx);
                      }}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                    >
                      <div className="flex justify-between items-start mb-2">
                        <h3 className="font-medium text-sm truncate pr-2">{ctx.name}</h3>
                        <span className={`shrink-0 w-2 h-2 rounded-full mt-1.5 ${ctx.status === 'active' ? 'bg-accent animate-pulse' : ctx.status === 'monitoring' ? 'bg-warning' : 'bg-text-muted'}`} />
                      </div>
                      <p className="text-xs text-text-secondary uppercase tracking-wider mb-3">{ctx.type}</p>
                      <div className="w-full h-1 bg-bg rounded-full overflow-hidden mb-3">
                        <div className="h-full bg-accent rounded-full" style={{ width: `${ctx.progress}%` }} />
                      </div>
                      <div className="flex gap-2 text-xs text-text-muted">
                        <span className="flex items-center gap-1"><Bot size={12} /> {ctx.agents.length}</span>
                        <span className="flex items-center gap-1"><Users size={12} /> {ctx.humans.length}</span>
                        <span className="flex items-center gap-1"><Wrench size={12} /> {ctx.hardware.length}</span>
                      </div>
                    </motion.div>
                  ))}

                  {/* Render Devices */}
                  {devices.map(device => (
                    <motion.div
                      key={device.id}
                      className={`absolute flex flex-col items-center justify-center cursor-pointer z-10 ${
                        selectedDevice?.id === device.id ? 'z-20' : ''
                      }`}
                      style={{ left: (device.x || 0) - 40, top: (device.y || 0) - 40 }}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedContext(null);
                        setSelectedDevice(device);
                      }}
                      whileHover={{ scale: 1.1 }}
                      whileTap={{ scale: 0.95 }}
                    >
                      <div className={`w-20 h-20 rounded-2xl flex items-center justify-center shadow-lg border-2 transition-colors relative ${
                        selectedDevice?.id === device.id 
                          ? 'bg-surface border-accent text-accent' 
                          : 'bg-surface border-border text-text-primary hover:border-accent/50'
                      }`}>
                        {device.status === 'online' && (
                          <div className="absolute inset-0 rounded-2xl border border-accent/30 animate-ping opacity-50"></div>
                        )}
                        <DeviceIcon type={device.type} name={device.name} />
                        <div className={`absolute -top-1 -right-1 w-3 h-3 rounded-full border-2 border-surface ${
                          device.status === 'online' ? 'bg-accent' : device.status === 'degraded' ? 'bg-warning' : 'bg-danger'
                        }`} />
                      </div>
                      <div className="mt-2 text-center bg-surface/80 backdrop-blur px-2 py-1 rounded border border-border">
                        <p className="text-xs font-medium whitespace-nowrap">{device.name}</p>
                        <p className="text-[10px] text-text-muted uppercase font-mono">{device.load.toFixed(0)}% LOAD</p>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </TransformComponent>
            </TransformWrapper>

            {/* Context Detail Panel */}
            <AnimatePresence>
              {selectedContext && (
                <motion.div
                  initial={{ x: '100%', opacity: 0 }}
                  animate={{ x: 0, opacity: 1 }}
                  exit={{ x: '100%', opacity: 0 }}
                  transition={{ type: 'spring', damping: 25, stiffness: 200 }}
                  className="absolute top-0 right-0 w-full lg:w-[1000px] xl:w-[1200px] h-full bg-surface/95 backdrop-blur-xl border-l border-border shadow-2xl z-30 flex flex-col"
                >
                  <div className="p-4 md:p-6 border-b border-border flex justify-between items-center bg-surface-hover/50 shrink-0">
                    <div>
                      <h2 className="font-medium text-xl md:text-2xl">{selectedContext.name}</h2>
                      <p className="text-sm text-text-secondary uppercase tracking-wider">{selectedContext.type} CONTEXT</p>
                    </div>
                    <div className="flex items-center gap-6">
                      <div className="hidden sm:block">
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-text-secondary font-medium uppercase tracking-wider">Progress</span>
                          <span className="font-mono text-accent">{selectedContext.progress}%</span>
                        </div>
                        <div className="w-48 h-2 bg-bg rounded-full overflow-hidden border border-border">
                          <div className="h-full bg-accent rounded-full" style={{ width: `${selectedContext.progress}%` }} />
                        </div>
                      </div>
                      <button onClick={() => setSelectedContext(null)} className="p-2 hover:bg-bg rounded-full transition-colors touch-manipulation">
                        <X size={24} />
                      </button>
                    </div>
                  </div>
                  
                  <div className="flex-1 flex overflow-hidden flex-col md:flex-row">
                    {/* Left: Context UI */}
                    <div className="flex-1 p-6 overflow-y-auto border-r border-border bg-bg/50">
                      {selectedContext.type === 'workshop' ? (
                        <div className="rounded-xl overflow-hidden border border-border bg-bg relative aspect-video shadow-lg">
                          <div className="absolute inset-0 bg-gradient-to-br from-surface to-bg flex items-center justify-center opacity-80">
                            <Camera size={48} className="text-text-muted" />
                          </div>
                          <div className="absolute top-4 left-4 bg-black/50 backdrop-blur-sm px-3 py-1.5 rounded text-xs font-mono text-accent flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-accent animate-pulse" /> LIVE
                          </div>
                          <div className="absolute bottom-4 left-4 text-xs font-mono text-text-secondary bg-black/50 backdrop-blur-sm px-3 py-1.5 rounded">
                            CAM-01 | 1080p | 30fps
                          </div>
                          {/* Mock bounding box overlay */}
                          <div className="absolute top-1/4 left-1/3 w-1/4 h-1/3 border-2 border-accent/50 bg-accent/10 rounded-sm">
                            <span className="absolute -top-6 left-0 text-[10px] bg-accent text-bg px-2 py-0.5 font-mono rounded-sm">PERSON 98%</span>
                          </div>
                        </div>
                      ) : selectedContext.type === 'hedgefund' ? (
                        <div className="space-y-4">
                           <div className="h-64 rounded-xl border border-border bg-surface flex items-center justify-center text-text-muted">
                             [Trading Chart Widget]
                           </div>
                           <div className="grid grid-cols-2 gap-4">
                             <div className="h-32 rounded-xl border border-border bg-surface flex items-center justify-center text-text-muted">[P&L]</div>
                             <div className="h-32 rounded-xl border border-border bg-surface flex items-center justify-center text-text-muted">[Risk Metrics]</div>
                           </div>
                        </div>
                      ) : (
                        <div className="w-full h-full border-2 border-dashed border-border rounded-xl flex items-center justify-center text-text-muted bg-surface-hover/30">
                          Context Interface
                        </div>
                      )}
                    </div>

                    {/* Middle: Operations / Interactions Mesh */}
                    <div className="w-full md:w-[400px] p-6 overflow-y-auto bg-surface-hover/20 shrink-0 flex flex-col">
                      <h3 className="text-sm font-medium text-text-secondary uppercase tracking-wider mb-6 flex items-center gap-2"><Activity size={16} /> Live Operations Mesh</h3>
                      
                      <div className="relative flex-1 min-h-[400px] border border-border rounded-xl bg-surface/50 overflow-hidden">
                        {/* Center Hub */}
                        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-16 h-16 rounded-full bg-surface border-2 border-accent flex items-center justify-center z-20 shadow-[0_0_30px_rgba(242,125,38,0.2)]">
                          <Layers size={24} className="text-accent" />
                        </div>
                        
                        {/* Draw SVG connections from center to nodes */}
                        <svg className="absolute inset-0 w-full h-full pointer-events-none z-0">
                          <g style={{ transform: 'translate(50%, 50%)' }}>
                            {[...selectedContext.agents, ...selectedContext.robots, ...selectedContext.hardware, ...selectedContext.humans].map((_, i, arr) => {
                              const angle = (i / arr.length) * Math.PI * 2 - Math.PI / 2;
                              const radius = 120;
                              const x = Math.cos(angle) * radius;
                              const y = Math.sin(angle) * radius;
                              return (
                                <line key={i} x1="0" y1="0" x2={x} y2={y} stroke="rgba(255,255,255,0.1)" strokeWidth="2" strokeDasharray="4 4" />
                              );
                            })}
                          </g>
                        </svg>

                        {/* Nodes */}
                        {[
                          ...selectedContext.agents.map(a => ({ ...a, type: 'agent', icon: Bot, color: 'text-accent', bg: 'bg-accent/10', border: 'border-accent/30' })),
                          ...selectedContext.robots.map(r => ({ ...r, type: 'robot', icon: Cpu, color: 'text-blue-400', bg: 'bg-blue-400/10', border: 'border-blue-400/30' })),
                          ...selectedContext.hardware.map(h => ({ ...h, type: 'hardware', icon: Wrench, color: 'text-emerald-400', bg: 'bg-emerald-400/10', border: 'border-emerald-400/30' })),
                          ...selectedContext.humans.map(h => ({ ...h, type: 'human', icon: Users, color: 'text-amber-400', bg: 'bg-amber-400/10', border: 'border-amber-400/30' }))
                        ].map((entity, i, arr) => {
                          const angle = (i / arr.length) * Math.PI * 2 - Math.PI / 2;
                          const radius = 120;
                          return (
                            <div 
                              key={entity.name} 
                              className="absolute w-24 -ml-12 -mt-12 flex flex-col items-center gap-2 z-10 group"
                              style={{ 
                                left: `calc(50% + ${Math.cos(angle) * radius}px)`, 
                                top: `calc(50% + ${Math.sin(angle) * radius}px)` 
                              }}
                            >
                              <div className={`w-10 h-10 rounded-full ${entity.bg} border ${entity.border} flex items-center justify-center ${entity.color} relative`}>
                                {entity.status === 'active' && <div className={`absolute inset-0 rounded-full border ${entity.border} animate-ping opacity-50`} />}
                                <entity.icon size={18} />
                              </div>
                              <div className="bg-surface/90 backdrop-blur border border-border px-2 py-1 rounded text-center shadow-lg opacity-0 group-hover:opacity-100 transition-opacity absolute top-full mt-2 w-32 pointer-events-none">
                                <p className={`font-medium text-xs ${entity.color}`}>{entity.name}</p>
                                <p className="text-[10px] text-text-secondary truncate">{entity.task}</p>
                              </div>
                            </div>
                          );
                        })}
                      </div>

                      {/* Artifacts */}
                      <div className="mt-8">
                        <h3 className="text-sm font-medium text-text-secondary uppercase tracking-wider mb-4 flex items-center gap-2"><FileText size={16} /> Artifacts</h3>
                        <div className="space-y-2">
                          {selectedContext.artifacts.map(art => (
                            <div key={art} className="p-3 bg-bg border border-border rounded-lg text-sm flex items-center justify-between hover:border-accent/50 cursor-pointer transition-colors group">
                              <span className="font-medium">{art}</span>
                              <Search size={14} className="text-text-muted group-hover:text-accent transition-colors" />
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    {/* Right: Deploy Toolbar */}
                    <div className="w-16 border-l border-border bg-surface-hover/50 flex flex-col items-center py-6 gap-4 shrink-0 hidden md:flex">
                      <div className="text-[10px] font-medium text-text-muted uppercase tracking-widest mb-4" style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}>Deploy Node</div>
                      
                      <button className="w-10 h-10 rounded-xl bg-surface border border-border flex items-center justify-center text-accent hover:border-accent hover:bg-accent/10 transition-colors cursor-grab active:cursor-grabbing group relative">
                        <Bot size={18} />
                        <span className="absolute right-full mr-2 bg-surface border border-border px-2 py-1 rounded text-xs opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50">Logic Agent</span>
                      </button>
                      <button className="w-10 h-10 rounded-xl bg-surface border border-border flex items-center justify-center text-blue-400 hover:border-blue-400 hover:bg-blue-400/10 transition-colors cursor-grab active:cursor-grabbing group relative">
                        <Search size={18} />
                        <span className="absolute right-full mr-2 bg-surface border border-border px-2 py-1 rounded text-xs opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50">Observer</span>
                      </button>
                      <button className="w-10 h-10 rounded-xl bg-surface border border-border flex items-center justify-center text-emerald-400 hover:border-emerald-400 hover:bg-emerald-400/10 transition-colors cursor-grab active:cursor-grabbing group relative">
                        <Shield size={18} />
                        <span className="absolute right-full mr-2 bg-surface border border-border px-2 py-1 rounded text-xs opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50">Security</span>
                      </button>
                      <button className="w-10 h-10 rounded-xl bg-surface border border-border flex items-center justify-center text-amber-400 hover:border-amber-400 hover:bg-amber-400/10 transition-colors cursor-grab active:cursor-grabbing group relative">
                        <Zap size={18} />
                        <span className="absolute right-full mr-2 bg-surface border border-border px-2 py-1 rounded text-xs opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50">Worker</span>
                      </button>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Device Detail Panel */}
            <AnimatePresence>
              {selectedDevice && (
                <motion.div
                  initial={{ x: '100%', opacity: 0 }}
                  animate={{ x: 0, opacity: 1 }}
                  exit={{ x: '100%', opacity: 0 }}
                  transition={{ type: 'spring', damping: 25, stiffness: 200 }}
                  className="absolute top-0 right-0 w-full sm:w-[400px] md:w-[500px] h-full bg-surface/95 backdrop-blur-xl border-l border-border shadow-2xl z-30 flex flex-col"
                >
                  <div className="p-4 md:p-6 border-b border-border flex justify-between items-start bg-surface-hover/50 shrink-0">
                    <div className="flex items-start gap-4">
                      <div className={`p-4 rounded-2xl ${selectedDevice.status === 'online' ? 'bg-accent/10 text-accent' : selectedDevice.status === 'degraded' ? 'bg-warning/10 text-warning' : 'bg-danger/10 text-danger'}`}>
                        <DeviceIcon type={selectedDevice.type} name={selectedDevice.name} />
                      </div>
                      <div>
                        <h2 className="font-medium text-xl md:text-2xl">{selectedDevice.name}</h2>
                        <p className="text-sm text-text-secondary uppercase tracking-wider">{selectedDevice.type} NODE</p>
                        <div className="mt-2 text-xs font-mono text-text-muted bg-bg px-2 py-1 rounded inline-block">{selectedDevice.id}</div>
                      </div>
                    </div>
                    <button onClick={() => setSelectedDevice(null)} className="p-2 hover:bg-bg rounded-full transition-colors touch-manipulation">
                      <X size={24} />
                    </button>
                  </div>
                  
                  <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-8">
                    {/* Status & Load */}
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-bg border border-border p-4 rounded-xl">
                        <div className="flex justify-between text-sm mb-2">
                          <span className="text-text-secondary">Compute Load</span>
                          <span className="font-mono">{selectedDevice.load.toFixed(1)}%</span>
                        </div>
                        <div className="w-full h-2 bg-surface rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${selectedDevice.load > 80 ? 'bg-danger' : selectedDevice.load > 50 ? 'bg-warning' : 'bg-accent'}`} style={{ width: `${selectedDevice.load}%` }}></div>
                        </div>
                      </div>
                      
                      <div className="bg-bg border border-border p-4 rounded-xl">
                        {selectedDevice.battery !== undefined ? (
                          <>
                            <div className="flex justify-between text-sm mb-2">
                              <span className="text-text-secondary">Battery</span>
                              <span className="font-mono">{selectedDevice.battery}%</span>
                            </div>
                            <div className="w-full h-2 bg-surface rounded-full overflow-hidden">
                              <div className={`h-full rounded-full ${selectedDevice.battery < 20 ? 'bg-danger' : 'bg-accent'}`} style={{ width: `${selectedDevice.battery}%` }}></div>
                            </div>
                          </>
                        ) : (
                          <>
                            <div className="flex justify-between text-sm mb-2">
                              <span className="text-text-secondary">Power</span>
                              <span className="font-mono text-accent">Mains</span>
                            </div>
                            <div className="w-full h-2 bg-surface rounded-full overflow-hidden">
                              <div className="h-full rounded-full bg-accent w-full"></div>
                            </div>
                          </>
                        )}
                      </div>
                    </div>

                    {/* Intelligence */}
                    <div>
                      <h3 className="text-sm font-medium text-text-secondary uppercase tracking-wider mb-4 flex items-center gap-2"><Brain size={16} /> Intelligence & Capabilities</h3>
                      <div className="space-y-4">
                        <div>
                          <p className="text-xs text-text-muted mb-2">MODELS LOADED</p>
                          <div className="flex flex-wrap gap-2">
                            {selectedDevice.models.map(m => (
                              <span key={m} className="px-3 py-1 bg-surface border border-border rounded-lg text-sm font-mono text-accent">{m}</span>
                            ))}
                          </div>
                        </div>
                        <div>
                          <p className="text-xs text-text-muted mb-2">CAPABILITIES</p>
                          <div className="flex flex-wrap gap-2">
                            {selectedDevice.capabilities.map(c => (
                              <span key={c} className="px-3 py-1 bg-surface-hover rounded-lg text-sm text-text-secondary">{c}</span>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Peripherals */}
                    <div>
                      <h3 className="text-sm font-medium text-text-secondary uppercase tracking-wider mb-4 flex items-center gap-2"><Radio size={16} /> Peripherals</h3>
                      <div className="space-y-2">
                        {selectedDevice.peripherals.map(p => (
                          <div key={p.name} className="flex items-center justify-between p-3 bg-bg border border-border rounded-lg">
                            <span className="text-sm font-medium">{p.name}</span>
                            <span className={`text-[10px] uppercase font-mono px-2 py-0.5 rounded ${p.status === 'active' ? 'bg-accent/10 text-accent' : p.status === 'error' ? 'bg-danger/10 text-danger' : 'bg-surface text-text-muted'}`}>
                              {p.status}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Files */}
                    <div>
                      <h3 className="text-sm font-medium text-text-secondary uppercase tracking-wider mb-4 flex items-center gap-2"><Database size={16} /> Local Storage</h3>
                      <div className="space-y-2">
                        {selectedDevice.files.map(f => (
                          <div key={f.name} className="flex items-center justify-between p-3 bg-bg border border-border rounded-lg hover:border-accent/50 cursor-pointer transition-colors group">
                            <div className="flex items-center gap-3">
                              {f.type === 'folder' ? <Layers size={16} className="text-text-muted group-hover:text-accent" /> : <FileText size={16} className="text-text-muted group-hover:text-accent" />}
                              <span className="text-sm font-medium">{f.name}</span>
                            </div>
                            <span className="text-xs font-mono text-text-muted">{f.size}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        );
      case 'memory':
        return (
          <div className="max-w-7xl mx-auto space-y-6 pb-24 h-[calc(100vh-8rem)] flex flex-col">
            <h2 className="text-2xl font-medium shrink-0">Memory Store Graph</h2>
            <div className="relative shrink-0">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted" size={20} />
              <input 
                type="text" 
                placeholder="Search semantic memory (e.g., 'What did I say about the drone frame?')" 
                className="w-full bg-surface border border-border rounded-xl py-4 pl-12 pr-4 text-sm focus:outline-none focus:border-accent/50 transition-colors min-h-[56px] touch-manipulation"
              />
            </div>
            <div className="flex-1 relative">
              <MemoryGraph />
              <div className="absolute bottom-4 left-4 bg-surface/80 backdrop-blur border border-border p-3 rounded-lg text-xs space-y-2">
                <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-[#10b981]"></span> Person</div>
                <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-[#f59e0b]"></span> Project</div>
                <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-[#3b82f6]"></span> Material</div>
                <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-[#8b5cf6]"></span> Location</div>
                <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-[#ef4444]"></span> Event</div>
              </div>
            </div>
          </div>
        );
      case 'logs':
        return (
          <div className="max-w-7xl mx-auto h-[calc(100vh-12rem)] flex flex-col pb-24">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-2xl font-medium">Stream Logs</h2>
              <div className="flex gap-2">
                <button className="px-3 py-1.5 bg-surface border border-border rounded text-sm hover:bg-surface-hover min-h-[44px] touch-manipulation">Filter</button>
                <button className="px-3 py-1.5 bg-surface border border-border rounded text-sm hover:bg-surface-hover min-h-[44px] touch-manipulation">Export</button>
              </div>
            </div>
            <div className="flex-1 bg-bg border border-border rounded-xl p-4 overflow-y-auto font-mono text-sm flex flex-col gap-1">
              {events.map(ev => (
                <div key={ev.id} className={`flex items-start gap-4 p-1.5 rounded hover:bg-surface ${ev.level === 'wake' ? 'text-warning' : ev.level === 'reasoning' ? 'text-accent' : 'text-text-secondary'}`}>
                  <span className="opacity-50 shrink-0 w-20">{ev.timestamp}</span>
                  <span className="w-32 shrink-0 truncate opacity-70">[{ev.source}]</span>
                  <span className="w-16 shrink-0 uppercase opacity-70 hidden sm:inline-block">{ev.type}</span>
                  <span className="flex-1">{ev.content}</span>
                </div>
              ))}
              <div ref={eventsEndRef} />
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-bg text-text-primary selection:bg-accent/30">
      
      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden relative">
        
        {/* Floating Navigation */}
        <div className="absolute top-6 left-1/2 -translate-x-1/2 z-40 flex items-center gap-2 bg-surface/80 backdrop-blur-xl border border-border p-1.5 rounded-2xl shadow-lg">
          <NavItem id="mesh" icon={Network} label="Zenoh Fabric" />
          <NavItem id="memory" icon={Database} label="Jing" />
          <NavItem id="logs" icon={Terminal} label="Fabric Noise" />
        </div>

        {/* Dynamic View Content */}
        <div className="flex-1 overflow-y-auto p-4 pt-24 md:p-8 md:pt-24">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentView}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
              className="h-full"
            >
              {renderView()}
            </motion.div>
          </AnimatePresence>
        </div>
        
        {/* Floating Agent Orb */}
        <AgentOrb />
      </main>
    </div>
  );
}
