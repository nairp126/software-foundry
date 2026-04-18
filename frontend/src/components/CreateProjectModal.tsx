import React, { useState } from 'react';
import { useProjectStore } from '../store/useProjectStore';
import { api } from '../lib/api';
import { X, Rocket, Terminal, Loader2, Sparkles } from 'lucide-react';

interface CreateProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const CreateProjectModal: React.FC<CreateProjectModalProps> = ({ isOpen, onClose }) => {
  const { setProjectId } = useProjectStore();
  const [name, setName] = useState('');
  const [requirements, setRequirements] = useState('');
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const project = await api.createProject(name, requirements);
      setProjectId(project.id);
      onClose();
    } catch (err) {
      console.error('Failed to create project:', err);
      alert('Failed to start project generation. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-slate-950/90 backdrop-blur-md animate-in fade-in duration-300">
      <div className="glass max-w-xl w-full rounded-2xl p-8 shadow-2xl border-white/10 scale-in-center">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
             <div className="p-2.5 bg-cyan-500/20 rounded-xl text-cyan-400">
                <Rocket size={24} />
             </div>
             <div>
                <h2 className="text-xl font-bold tracking-tight">Generate New Software</h2>
                <p className="text-xs text-slate-500 uppercase font-bold tracking-widest mt-0.5">Foundry Engine v1.0</p>
             </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-white/5 rounded-full text-slate-500 transition-colors">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-6">
          <div className="flex flex-col gap-2">
            <label className="text-[10px] uppercase font-bold tracking-widest text-slate-500 flex items-center gap-2 px-1">
               Project Name
            </label>
            <input
              autoFocus
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. My Awesome API"
              className="w-full bg-slate-900/50 border border-white/5 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-cyan-500/50 transition-all placeholder:text-slate-700"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-[10px] uppercase font-bold tracking-widest text-slate-500 flex items-center gap-2 px-1">
               System Requirements
            </label>
            <textarea
              required
              value={requirements}
              onChange={(e) => setRequirements(e.target.value)}
              placeholder="Describe what you want to build in detail..."
              className="w-full bg-slate-900/50 border border-white/5 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-cyan-500/50 transition-all placeholder:text-slate-700 h-40 resize-none leading-relaxed"
            />
          </div>

          <div className="mt-4 flex flex-col gap-4">
             <button
                type="submit"
                disabled={loading || !name || !requirements}
                className="w-full h-14 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 disabled:opacity-50 disabled:grayscale rounded-xl font-bold flex items-center justify-center gap-3 transition-all shadow-xl shadow-cyan-900/20 group"
             >
                {loading ? (
                  <Loader2 className="animate-spin" size={20} />
                ) : (
                  <>
                    <Sparkles size={20} className="group-hover:animate-pulse" />
                    <span>Ignite Generation Pipeline</span>
                  </>
                )}
             </button>
             
             <div className="flex items-center gap-2 justify-center py-2 opacity-40">
                <Terminal size={12} className="text-slate-500" />
                <span className="text-[10px] uppercase font-bold tracking-widest text-slate-500">FastAPI + Redis + Neo4j Connected</span>
             </div>
          </div>
        </form>
      </div>
    </div>
  );
};
