import React from 'react';
import { useProjectStore } from '../store/useProjectStore';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { 
  X, 
  FileCode, 
  Settings, 
  Hash, 
  Zap, 
  Info,
  Maximize2,
  Minimize2,
  ExternalLink
} from 'lucide-react';

export const InspectorPanel: React.FC = () => {
  const { 
    graphData, 
    selectedNodeId, 
    selectedLinkId, 
    setSelectedNodeId, 
    setSelectedLinkId 
  } = useProjectStore();

  const selectedNode = graphData.nodes?.find(n => n.id === selectedNodeId);
  const selectedLink = graphData.links?.find(l => l.id === selectedLinkId);

  const close = () => {
    setSelectedNodeId(null);
    setSelectedLinkId(null);
  };

  if (!selectedNode && !selectedLink) return null;

  return (
    <div className="fixed top-20 right-8 bottom-8 w-[500px] z-40 animate-in slide-in-from-right duration-500">
      <div className="h-full glass rounded-3xl border-white/10 shadow-2xl flex flex-col overflow-hidden bg-slate-950/40">
        
        {/* Header */}
        <div className="p-6 border-b border-white/5 flex items-center justify-between bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-slate-900 rounded-xl border border-white/10">
              {selectedNode ? <FileCode className="text-cyan-400" size={20} /> : <Info className="text-blue-400" size={20} />}
            </div>
            <div>
              <h3 className="text-sm font-bold uppercase tracking-widest text-slate-100 truncate w-64">
                {selectedNode ? selectedNode.name : selectedLink?.type}
              </h3>
              <p className="text-[10px] text-slate-500 font-mono uppercase tracking-tighter">
                {selectedNode ? `${selectedNode.label} NODE` : 'RELATIONSHIP'}
              </p>
            </div>
          </div>
          <button 
            onClick={close}
            className="p-2 hover:bg-white/5 rounded-full transition-colors text-slate-500 hover:text-white"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 custom-scrollbar">
          
          {selectedNode && (
            <div className="flex flex-col gap-6">
              
              {/* Properties Grid */}
              <div className="grid grid-cols-2 gap-3">
                 {selectedNode.complexity && (
                   <div className="bg-white/[0.03] p-3 rounded-xl border border-white/5">
                      <div className="flex items-center gap-2 text-[10px] font-bold text-slate-500 uppercase mb-1">
                        <Zap size={12} className="text-amber-500" /> Complexity
                      </div>
                      <div className="text-lg font-mono text-slate-200">{selectedNode.complexity}</div>
                   </div>
                 )}
                 {selectedNode.file_path && (
                   <div className="bg-white/[0.03] p-3 rounded-xl border border-white/5 col-span-2">
                      <div className="flex items-center gap-2 text-[10px] font-bold text-slate-500 uppercase mb-1">
                        <Hash size={12} className="text-blue-500" /> Location
                      </div>
                      <div className="text-xs font-mono text-slate-400 break-all">{selectedNode.file_path}</div>
                   </div>
                 )}
              </div>

              {/* Code Section */}
              {selectedNode.content && (
                <div className="flex flex-col gap-3">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] font-bold text-slate-500 uppercase flex items-center gap-2">
                        <Settings size={12} /> Source Content
                    </label>
                    <button className="p-1 hover:bg-white/5 rounded text-slate-500 hover:text-white transition-colors">
                      <Maximize2 size={12} />
                    </button>
                  </div>
                  <div className="rounded-xl overflow-hidden border border-white/10 bg-black/40 text-[11px]">
                    <SyntaxHighlighter 
                      language={selectedNode.language || "python"} 
                      style={vscDarkPlus}
                      customStyle={{ 
                        margin: 0, 
                        padding: '1.5rem', 
                        background: 'transparent',
                        maxHeight: '400px'
                      }}
                      wrapLines={true}
                    >
                      {selectedNode.content}
                    </SyntaxHighlighter>
                  </div>
                </div>
              )}

              {/* Metadata */}
              {selectedNode.metadata && Object.keys(selectedNode.metadata).length > 0 && (
                 <div className="flex flex-col gap-3">
                    <label className="text-[10px] font-bold text-slate-500 uppercase flex items-center gap-2">
                        <Info size={12} /> Extended Metadata
                    </label>
                    <div className="bg-white/[0.03] p-4 rounded-xl border border-white/5 text-[11px] font-mono text-slate-400 space-y-1">
                       {Object.entries(selectedNode.metadata).map(([k, v]: [string, any]) => (
                         <div key={k} className="flex justify-between">
                           <span className="text-slate-600">{k}:</span>
                           <span>{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
                         </div>
                       ))}
                    </div>
                 </div>
              )}
            </div>
          )}

          {selectedLink && (
            <div className="flex flex-col gap-6">
               <div className="bg-blue-500/10 p-6 rounded-2xl border border-blue-500/20 text-center">
                  <ExternalLink size={32} className="mx-auto text-blue-400 mb-3 opacity-50" />
                  <h4 className="text-sm font-bold text-slate-200">Semantic Link Detected</h4>
                  <p className="text-xs text-slate-400 mt-1">This relationship defines the interaction between these two foundry nodes.</p>
               </div>
               
               <div className="bg-white/[0.03] p-4 rounded-xl border border-white/5">
                  <div className="text-[10px] font-bold text-slate-500 uppercase mb-2">Relationship Metadata</div>
                  <div className="text-xs font-mono text-slate-400 space-y-2">
                    <div className="flex justify-between">
                      <span className="text-slate-600">Type:</span>
                      <span className="text-blue-400">{selectedLink.type}</span>
                    </div>
                    {selectedLink.metadata && Object.entries(selectedLink.metadata).map(([k, v]: [string, any]) => (
                      <div key={k} className="flex justify-between">
                        <span className="text-slate-600">{k}:</span>
                        <span>{String(v)}</span>
                      </div>
                    ))}
                  </div>
               </div>
            </div>
          )}

        </div>

        {/* Footer Actions */}
        <div className="p-6 border-t border-white/5 bg-white/[0.01]">
          <button 
            className="w-full h-12 bg-white/5 hover:bg-white/10 rounded-xl text-xs font-bold uppercase tracking-widest transition-all border border-white/5 hover:border-white/20"
            onClick={close}
          >
            Collapse Detail
          </button>
        </div>

      </div>
    </div>
  );
};
