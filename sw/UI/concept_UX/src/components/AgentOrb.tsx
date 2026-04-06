import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Mic, X, Send, Brain } from 'lucide-react';

export default function AgentOrb() {
  const [isOpen, setIsOpen] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([
    { id: 1, role: 'agent', text: 'Velvet Nadir online. How can I assist you?' }
  ]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isOpen]);

  const handleSend = () => {
    if (!input.trim()) return;
    const newMsg = { id: Date.now(), role: 'user', text: input };
    setMessages(prev => [...prev, newMsg]);
    setInput('');
    setIsListening(false);
    
    // Mock response
    setTimeout(() => {
      setIsSpeaking(true);
      setMessages(prev => [...prev, { id: Date.now(), role: 'agent', text: 'Processing your request across active contexts...' }]);
      setTimeout(() => setIsSpeaking(false), 2000);
    }, 1000);
  };

  const orbStateClass = isSpeaking 
    ? 'animate-liquid-speaking' 
    : isListening 
      ? 'animate-liquid-listening' 
      : 'animate-liquid-idle';

  return (
    <>
      <AnimatePresence>
        {!isOpen && (
          <motion.button
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            onClick={() => setIsOpen(true)}
            className="fixed bottom-8 left-8 w-32 h-32 flex items-center justify-center z-50 group touch-manipulation"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            {/* Outer glow */}
            <div className="absolute inset-0 bg-accent/20 blur-2xl rounded-full group-hover:bg-accent/40 transition-all duration-500"></div>
            
            <div className="relative w-28 h-28 flex items-center justify-center" style={{ perspective: '800px' }}>
              {/* Outer 3D Sphere */}
              <div className={`absolute inset-0 transform-style-3d ${isListening || isSpeaking ? 'animate-[spin3d_3s_linear_infinite]' : 'animate-[spin3d_12s_linear_infinite]'}`}>
                <div className="absolute inset-0 rounded-full border-2 border-accent/40 shadow-[0_0_15px_rgba(16,185,129,0.4)_inset,0_0_15px_rgba(16,185,129,0.4)]" style={{ transform: 'rotateX(90deg)' }}></div>
                <div className="absolute inset-0 rounded-full border-2 border-accent/40 shadow-[0_0_15px_rgba(16,185,129,0.4)_inset,0_0_15px_rgba(16,185,129,0.4)]" style={{ transform: 'rotateY(90deg)' }}></div>
                <div className="absolute inset-0 rounded-full border-2 border-accent/40 shadow-[0_0_15px_rgba(16,185,129,0.4)_inset,0_0_15px_rgba(16,185,129,0.4)]" style={{ transform: 'rotateX(45deg) rotateY(45deg)' }}></div>
                <div className="absolute inset-0 rounded-full border-2 border-accent/40 shadow-[0_0_15px_rgba(16,185,129,0.4)_inset,0_0_15px_rgba(16,185,129,0.4)]" style={{ transform: 'rotateX(-45deg) rotateY(45deg)' }}></div>
              </div>

              {/* Inner 3D Sphere (Spins opposite) */}
              <div className={`absolute inset-4 transform-style-3d ${isListening || isSpeaking ? 'animate-[spin3dReverse_2s_linear_infinite]' : 'animate-[spin3dReverse_8s_linear_infinite]'}`}>
                <div className="absolute inset-0 rounded-full border border-accent/60 shadow-[0_0_10px_rgba(16,185,129,0.6)_inset]" style={{ transform: 'rotateX(90deg)' }}></div>
                <div className="absolute inset-0 rounded-full border border-accent/60 shadow-[0_0_10px_rgba(16,185,129,0.6)_inset]" style={{ transform: 'rotateY(90deg)' }}></div>
                <div className="absolute inset-0 rounded-full border border-accent/60 shadow-[0_0_10px_rgba(16,185,129,0.6)_inset]" style={{ transform: 'rotateZ(90deg)' }}></div>
              </div>

              {/* Center Core */}
              <div className={`relative z-10 w-12 h-12 bg-surface border border-accent/80 rounded-full flex items-center justify-center shadow-[0_0_30px_rgba(16,185,129,0.8)] ${isSpeaking ? 'animate-pulse scale-110' : ''} transition-transform duration-300`}>
                <Brain size={24} className={`text-accent drop-shadow-[0_0_10px_rgba(16,185,129,1)] ${isListening ? 'animate-pulse' : ''}`} />
              </div>
            </div>
          </motion.button>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className="fixed bottom-6 left-6 w-[calc(100vw-3rem)] md:w-[400px] h-[600px] max-h-[85vh] bg-surface/95 backdrop-blur-2xl border border-accent/30 rounded-3xl shadow-[0_0_50px_rgba(0,0,0,0.5)] flex flex-col z-50 overflow-hidden"
          >
            {/* Header */}
            <div className="h-16 border-b border-border flex items-center justify-between px-4 bg-surface-hover/50 shrink-0">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 relative flex items-center justify-center" style={{ perspective: '200px' }}>
                  <div className="absolute inset-0 transform-style-3d animate-[spin3d_6s_linear_infinite]">
                    <div className="absolute inset-0 rounded-full border border-accent/40 shadow-[0_0_5px_rgba(16,185,129,0.4)_inset]" style={{ transform: 'rotateX(90deg)' }}></div>
                    <div className="absolute inset-0 rounded-full border border-accent/40 shadow-[0_0_5px_rgba(16,185,129,0.4)_inset]" style={{ transform: 'rotateY(90deg)' }}></div>
                  </div>
                  <Brain size={16} className="text-accent relative z-10" />
                </div>
                <div>
                  <h3 className="font-medium text-sm">Velvet Agent</h3>
                  <p className="text-xs text-text-secondary font-mono">{isListening ? 'Listening...' : isSpeaking ? 'Speaking...' : 'Idle'}</p>
                </div>
              </div>
              <button 
                onClick={() => setIsOpen(false)}
                className="p-2 rounded-full hover:bg-bg text-text-secondary hover:text-text-primary transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center touch-manipulation"
              >
                <X size={20} />
              </button>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.map(msg => (
                <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[80%] p-3 rounded-2xl text-sm ${
                    msg.role === 'user' 
                      ? 'bg-accent text-bg rounded-br-sm' 
                      : 'bg-bg border border-border text-text-primary rounded-bl-sm'
                  }`}>
                    {msg.text}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t border-border bg-surface-hover/30 shrink-0">
              <div className="flex items-center gap-2">
                <button 
                  onClick={() => setIsListening(!isListening)}
                  className={`p-3 rounded-full transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center touch-manipulation ${isListening ? 'bg-danger/20 text-danger' : 'bg-bg border border-border text-text-secondary hover:text-text-primary'}`}
                >
                  <Mic size={18} className={isListening ? 'animate-pulse' : ''} />
                </button>
                <div className="flex-1 relative">
                  <input 
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                    placeholder="Ask Velvet..."
                    className="w-full bg-bg border border-border rounded-full py-3 pl-4 pr-12 text-sm focus:outline-none focus:border-accent/50 transition-colors"
                  />
                  <button 
                    onClick={handleSend}
                    className="absolute right-1 top-1 bottom-1 aspect-square rounded-full bg-accent/10 text-accent hover:bg-accent hover:text-bg transition-colors flex items-center justify-center touch-manipulation"
                  >
                    <Send size={16} />
                  </button>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
