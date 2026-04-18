import React, { useState } from 'react';
import { useProjectStore } from './store/useProjectStore';
import { useAgentSocket } from './hooks/useAgentSocket';
import { GraphVisualizer } from './components/GraphVisualizer';
import { ApprovalGate } from './components/ApprovalGate';
import { InspectorPanel } from './components/InspectorPanel';
import { CreateProjectModal } from './components/CreateProjectModal';
import { ProjectSidebar } from './components/ProjectSidebar';
import { 
  Bot, 
  Terminal, 
  Cpu, 
  CheckCircle2, 
  Activity,
  Box,
  Layout,
  Code2,
  ShieldCheck,
  RefreshCw,
  Rocket,
  Share2,
  History
} from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const AgentIcon = ({ agent, size = 20 }: { agent: string, size?: number }) => {
  switch (agent) {
    case 'ProductManager': return <Box size={size} className="text-blue-400" />;
    case 'Architect': return <Layout size={size} className="text-purple-400" />;
    case 'Engineer': return <Code2 size={size} className="text-emerald-400" />;
    case 'CodeReview': return <ShieldCheck size={size} className="text-amber-400" />;
    case 'Reflexion': return <RefreshCw size={size} className="text-rose-400" />;
    case 'DevOps': return <Rocket size={size} className="text-cyan-400" />;
    default: return <Bot size={size} />;
  }
};

const PipelineStep = ({ label, active, completed, agent }: { label: string, active: boolean, completed: boolean, agent: string }) => (
  <div className="flex flex-col items-center gap-2 relative z-10">
    <div className={cn(
      "w-12 h-12 rounded-xl flex items-center justify-center border-2 transition-all duration-700",
      active ? "border-cyan-500 bg-cyan-500/20 shadow-[0_0_20px_rgba(6,182,212,0.4)] scale-110" : 
      completed ? "border-emerald-500 bg-emerald-500/10" : "border-slate-800 bg-slate-900/50"
    )}>
      {completed ? <CheckCircle2 size={24} className="text-emerald-500" /> : <AgentIcon agent={agent} size={24} />}
    </div>
    <span className={cn(
      "text-[10px] font-bold uppercase tracking-[0.2em] transition-colors duration-500",
      active ? "text-cyan-400" : completed ? "text-emerald-500/70" : "text-slate-600"
    )}>{label}</span>
  </div>
);

const PipelineConnector = ({ active, completed }: { active: boolean, completed: boolean }) => (
  <div className="flex-1 h-[2px] bg-slate-800/50 mx-[-4px] mb-6 relative overflow-hidden min-w-[30px]">
    <div className={cn(
      "absolute inset-0 bg-gradient-to-r from-emerald-500 via-cyan-500 to-blue-500 transition-all duration-1000",
      completed ? "translate-x-0 opacity-100" : active ? "animate-flow opacity-60" : "-translate-x-full opacity-0"
    )} />
    {active && (
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-flow" style={{ animationDuration: '1.5s' }} />
    )}
  </div>
);

function App() {
  const { projectId, status, thoughts, messages, setProjectId, reset } = useProjectStore();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  useAgentSocket(projectId);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50 font-sans selection:bg-cyan-500/30 overflow-x-hidden">
      <ApprovalGate />
      <InspectorPanel />
      <ProjectSidebar isOpen={isSidebarOpen} onToggle={() => setIsSidebarOpen(!isSidebarOpen)} />
      <CreateProjectModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
      
      <header className="h-16 border-b border-white/5 flex items-center justify-between px-8 glass sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <div className="bg-gradient-to-br from-cyan-500 to-purple-600 p-2 rounded-lg">
            <Cpu size={24} className="text-white" />
          </div>
          <h1 className="text-xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">
            Software Foundry
          </h1>
        </div>
        
        <div className="flex items-center gap-4">
          <button 
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className={cn(
              "flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all",
              isSidebarOpen ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/30" : "text-slate-400 hover:bg-white/5"
            )}
          >
            <History size={16} />
            <span className="text-xs font-bold uppercase tracking-widest">History</span>
          </button>

          {!projectId ? (
            <button 
              onClick={() => setIsModalOpen(true)}
              className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-sm font-semibold rounded-md transition-colors shadow-lg shadow-cyan-900/20"
            >
              Start New Project
            </button>
          ) : (
            <div className="flex items-center gap-3">
               <button 
                  onClick={reset}
                  className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-[10px] font-bold uppercase tracking-wider rounded border border-white/5 transition-colors"
                >
                  Terminate Session
                </button>
               <div className="hidden md:flex items-center gap-2 px-3 py-1 bg-slate-900 border border-white/5 rounded-full">
                <span className="text-[10px] text-slate-500 font-mono tracking-tighter uppercase">ID: {projectId.slice(0, 8)}...</span>
              </div>
              <div className="flex items-center gap-2 px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full">
                <div className={cn("w-2 h-2 rounded-full bg-emerald-500", status !== 'completed' && "animate-pulse")} />
                <span className="text-xs text-emerald-400 font-medium uppercase tracking-wider">{status === 'completed' ? 'Ready' : 'Live'}</span>
              </div>
            </div>
          )}
        </div>
      </header>

      <main className={cn(
        "p-6 h-[calc(100vh-64px)] grid grid-cols-12 gap-6 transition-all duration-300",
        isSidebarOpen ? "ml-72" : "ml-0"
      )}>
        
        {/* Step Visualizer Panel (Left/Full) */}
        <div className="col-span-12 flex flex-col gap-6">
           <section className="glass rounded-2xl p-8 flex items-center relative overflow-hidden">
            <div className="absolute top-0 right-0 w-64 h-64 bg-cyan-500/5 blur-[100px] -z-10" />
            
            <PipelineStep agent="ProductManager" label="PM" active={status === 'running_pm'} completed={['running_architect', 'running_engineer', 'running_code_review', 'running_reflexion', 'running_devops', 'completed'].includes(status)} />
            <PipelineConnector active={status === 'running_pm'} completed={['running_architect', 'running_engineer', 'running_code_review', 'running_reflexion', 'running_devops', 'completed'].includes(status)} />
            
            <PipelineStep agent="Architect" label="Architect" active={status === 'running_architect' || status === 'paused'} completed={['running_engineer', 'running_code_review', 'running_reflexion', 'running_devops', 'completed'].includes(status)} />
            <PipelineConnector active={status === 'running_architect'} completed={['running_engineer', 'running_code_review', 'running_reflexion', 'running_devops', 'completed'].includes(status)} />
            
            <PipelineStep agent="Engineer" label="Engineer" active={status === 'running_engineer'} completed={['running_code_review', 'running_reflexion', 'running_devops', 'completed'].includes(status)} />
            <PipelineConnector active={status === 'running_engineer'} completed={['running_code_review', 'running_reflexion', 'running_devops', 'completed'].includes(status)} />
            
            <PipelineStep agent="CodeReview" label="Review" active={status === 'running_code_review'} completed={['running_reflexion', 'running_devops', 'completed'].includes(status)} />
            <PipelineConnector active={status === 'running_code_review'} completed={['running_reflexion', 'running_devops', 'completed'].includes(status)} />
            
            <PipelineStep agent="Reflexion" label="Reflexion" active={status === 'running_reflexion'} completed={['running_devops', 'completed'].includes(status)} />
            <PipelineConnector active={status === 'running_reflexion'} completed={['running_devops', 'completed'].includes(status)} />
            
            <PipelineStep agent="DevOps" label="DevOps" active={status === 'running_devops'} completed={status === 'completed'} />
            <PipelineConnector active={status === 'running_devops'} completed={status === 'completed'} />

            <div className="flex flex-col items-center gap-2 relative z-10">
              <div className={cn(
                "w-12 h-12 rounded-full flex items-center justify-center border-2 transition-all duration-1000",
                status === 'completed' ? "border-cyan-400 bg-cyan-400/20 shadow-[0_0_30px_rgba(34,211,238,0.6)]" : "border-slate-800 bg-slate-900/50"
              )}>
                <Rocket size={24} className={status === 'completed' ? "text-cyan-400" : "text-slate-600"} />
              </div>
              <span className={cn(
                "text-[10px] font-bold uppercase tracking-[0.2em]",
                status === 'completed' ? "text-cyan-400" : "text-slate-600"
              )}>Finished</span>
            </div>
          </section>

          {status === 'completed' && (
            <div className="mt-8 p-6 bg-emerald-500/10 border border-emerald-500/20 rounded-xl flex items-center justify-between animate-in fade-in slide-in-from-bottom-4 duration-500">
              <div className="flex items-center gap-4">
                <div className="bg-emerald-500 p-3 rounded-full shadow-lg shadow-emerald-500/20">
                  <ShieldCheck size={24} className="text-white" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white">Project Successfully Completed!</h3>
                  <p className="text-sm text-emerald-400/80">All agents have finished. Your codebase is ready in the generated_projects folder.</p>
                </div>
              </div>
              <div className="flex gap-3">
                <button 
                  onClick={() => setIsSidebarOpen(true)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white text-sm font-semibold rounded-lg border border-white/5 transition-colors"
                >
                  View History
                </button>
                <button 
                  onClick={reset}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold rounded-lg transition-colors shadow-lg shadow-emerald-900/20"
                >
                  New Project
                </button>
              </div>
            </div>
          )}

          <div className="mt-8 grid grid-cols-12 gap-8 flex-1 min-h-0">

        {/* The Loom: Agent Telemetry (Left) */}
        <div className="col-span-12 lg:col-span-4 flex flex-col gap-4 overflow-hidden">
          <div className="flex items-center gap-2 ml-1">
            <Bot size={18} className="text-slate-400" />
            <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-400">Agent Telemetry</h2>
          </div>
          
          <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar space-y-3 pb-4">
            {thoughts.length === 0 && (
              <div className="glass rounded-xl p-8 text-center text-slate-500 italic">
                Waiting for agents to broadcast thoughts...
              </div>
            )}
            {thoughts.map((thought, idx) => (
              <div 
                key={idx} 
                className={cn(
                  "glass rounded-xl p-4 flex gap-4 transition-all duration-300 animate-in fade-in slide-in-from-left-4",
                  idx === 0 ? "border-cyan-500/30 bg-cyan-500/5 shadow-xl" : "opacity-60"
                )}
              >
                <div className="shrink-0 mt-1">
                  <AgentIcon agent={thought.agent} />
                </div>
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm tracking-tight">{thought.agent}</span>
                    <span className="text-[10px] text-slate-500 font-mono italic underline">{new Date(thought.timestamp).toLocaleTimeString()}</span>
                  </div>
                  <p className="text-sm text-slate-300 leading-relaxed font-medium">
                    {thought.thought}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Center: Graph & Console (Center/Right Wide) */}
        <div className="col-span-12 lg:col-span-8 grid grid-rows-2 gap-6 overflow-hidden">
          {/* Graph Visualization */}
          <div className="flex flex-col gap-3 min-h-0">
             <div className="flex items-center gap-2 ml-1">
                <Share2 size={18} className="text-slate-400" />
                <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-400">Knowledge Graph View</h2>
              </div>
              <GraphVisualizer />
          </div>

          {/* Console / Terminal */}
          <section className="glass rounded-2xl flex flex-col min-h-0 overflow-hidden border-slate-800/50">
            <div className="p-3 border-b border-white/5 flex items-center justify-between bg-white/[0.02] shrink-0">
              <div className="flex items-center gap-2 text-slate-400">
                <Terminal size={14} />
                <span className="text-[10px] font-bold uppercase tracking-wider">Project Console</span>
              </div>
              <div className="flex gap-1.5 opacity-30">
                <div className="w-2 h-2 rounded-full bg-slate-500" />
                <div className="w-2 h-2 rounded-full bg-slate-500" />
                <div className="w-2 h-2 rounded-full bg-slate-500" />
              </div>
            </div>
            
            <div className="flex-1 p-5 overflow-y-auto font-mono text-[11px] leading-relaxed flex flex-col gap-1.5 bg-black/20 custom-scrollbar">
              {messages.map((msg, i) => (
                <div key={i} className="flex gap-4 group">
                  <span className="text-slate-700 select-none w-6 shrink-0 group-hover:text-slate-500 transition-colors">[{i+1}]</span>
                  <span className="text-slate-400 group-hover:text-slate-200 transition-colors">{msg}</span>
                </div>
              ))}
              {messages.length === 0 && (
                <div className="text-slate-800 italic">No console output received...</div>
              )}
            </div>
          </section>
          </div>
        </div>
        </div>
      </main>
    </div>
  );
}

export default App;
