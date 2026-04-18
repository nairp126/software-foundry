import React, { useEffect } from 'react';
import { useProjectStore } from '../store/useProjectStore';
import { Folder, Clock, CheckCircle2, Activity, ChevronLeft, ChevronRight } from 'lucide-react';
import { clsx } from 'clsx';

interface ProjectSidebarProps {
  isOpen: boolean;
  onToggle: () => void;
}

export const ProjectSidebar: React.FC<ProjectSidebarProps> = ({ isOpen, onToggle }) => {
  const { projectList, fetchProjects, setProjectId, projectId } = useProjectStore();

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const getStatusIcon = (status: string) => {
    if (status === 'completed') return <CheckCircle2 size={14} className="text-emerald-500" />;
    return <Activity size={14} className="text-cyan-500 animate-pulse" />;
  };

  return (
    <aside 
      className={clsx(
        "fixed left-0 top-16 bottom-0 z-40 transition-all duration-300 border-r border-white/5 glass",
        isOpen ? "w-72" : "w-0 overflow-hidden"
      )}
    >
      <div className="flex flex-col h-full w-72">
        <div className="p-4 border-b border-white/5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Folder size={18} className="text-slate-400" />
            <h2 className="text-sm font-bold uppercase tracking-widest text-slate-400">Project History</h2>
          </div>
          <button onClick={onToggle} className="p-1 hover:bg-white/5 rounded">
             <ChevronLeft size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1">
          {projectList.length === 0 && (
            <div className="p-8 text-center text-slate-500 text-xs italic">
              No past projects found.
            </div>
          )}
          {projectList.map((project) => (
            <button
              key={project.id}
              onClick={() => setProjectId(project.id)}
              className={clsx(
                "w-full text-left p-3 rounded-xl transition-all duration-200 group flex flex-col gap-1",
                projectId === project.id 
                  ? "bg-cyan-500/10 border border-cyan-500/30" 
                  : "hover:bg-white/5 border border-transparent"
              )}
            >
              <div className="flex items-center justify-between">
                <span className={clsx(
                  "text-sm font-semibold truncate",
                  projectId === project.id ? "text-cyan-400" : "text-slate-300"
                )}>
                  {project.name}
                </span>
                {getStatusIcon(project.status)}
              </div>
              <div className="flex items-center gap-2 text-[10px] text-slate-500">
                <Clock size={10} />
                <span>{new Date(project.created_at).toLocaleDateString()}</span>
                <span className="opacity-30">|</span>
                <span className="uppercase tracking-tighter">{project.status.replace('running_', '')}</span>
              </div>
            </button>
          ))}
        </div>
      </div>
      
    </aside>
  );
};
