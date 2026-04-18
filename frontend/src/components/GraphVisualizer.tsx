import React, { useMemo, useRef, useCallback, useEffect } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { useProjectStore } from '../store/useProjectStore';
import { Box } from 'lucide-react';

export const GraphVisualizer: React.FC = () => {
  const fgRef = useRef<any>(null);
  const { graphData, selectedNodeId, selectedLinkId, setSelectedNodeId, setSelectedLinkId } = useProjectStore();

  useEffect(() => {
    if (graphData.nodes.length > 0 && fgRef.current) {
      // Auto-zoom to fit nodes on initial load or data change
      setTimeout(() => {
        fgRef.current.zoomToFit(400, 50);
      }, 500);
    }
  }, [graphData.nodes.length]);

  const colorMap: Record<string, string> = {
    Project: '#ffffff',
    Requirement: '#60a5fa', // Blue
    Component: '#c084fc',   // Purple
    Class: '#a78bfa',
    Function: '#818cf8',
    Artifact: '#34d399',    // Emerald
    ErrorFix: '#fb7185',    // Rose
  };

  const processedData = useMemo(() => {
    if (!graphData.nodes) return { nodes: [], links: [] };
    
    return {
      nodes: graphData.nodes.map(n => ({
        ...n,
        color: colorMap[n.label] || '#94a3b8',
        val: n.label === 'Project' ? 5 : 2
      })),
      links: graphData.links.map(l => ({
        ...l,
        color: l.id === selectedLinkId ? '#60a5fa' : '#334155',
        curvature: 0.1
      }))
    };
  }, [graphData, selectedLinkId]);

  const handleNodeClick = useCallback((node: any) => {
    setSelectedNodeId(node.id);
    
    // Zoom to node
    if (fgRef.current) {
        fgRef.current.centerAt(node.x, node.y, 1000);
        fgRef.current.zoom(2.5, 1000);
    }
  }, [setSelectedNodeId]);

  const handleLinkClick = useCallback((link: any) => {
    setSelectedLinkId(link.id);
  }, [setSelectedLinkId]);

  const handleBackgroundClick = useCallback(() => {
    setSelectedNodeId(null);
    setSelectedLinkId(null);
  }, [setSelectedNodeId, setSelectedLinkId]);

  if (graphData.nodes.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-slate-600 glass rounded-2xl">
        <Box size={48} className="mb-4 opacity-20" />
        <p className="text-sm font-medium">Knowledge Graph is empty</p>
        <p className="text-xs opacity-60">Nodes will appear as agents ingest code</p>
      </div>
    );
  }

  return (
    <div className="flex-1 glass rounded-2xl overflow-hidden relative group">
      <div className="absolute top-4 left-4 z-10 flex flex-col gap-2 pointer-events-none">
         <div className="flex items-center gap-2 px-2 py-1 bg-black/40 rounded border border-white/5 text-[10px]">
            <div className="w-2 h-2 rounded-full bg-blue-400" /> <span>Requirements</span>
         </div>
         <div className="flex items-center gap-2 px-2 py-1 bg-black/40 rounded border border-white/5 text-[10px]">
            <div className="w-2 h-2 rounded-full bg-purple-400" /> <span>Components</span>
         </div>
         <div className="flex items-center gap-2 px-2 py-1 bg-black/40 rounded border border-white/5 text-[10px]">
            <div className="w-2 h-2 rounded-full bg-emerald-400" /> <span>Files</span>
         </div>
      </div>

      <div className="absolute bottom-4 right-4 z-10 opacity-0 group-hover:opacity-100 transition-opacity">
         <button 
           onClick={() => fgRef.current?.zoomToFit(400, 50)}
           className="p-2 bg-slate-900 border border-white/10 rounded-lg hover:bg-slate-800 text-[10px] font-bold uppercase tracking-wider"
         >
           Fit View
         </button>
      </div>

      <ForceGraph2D
        ref={fgRef}
        graphData={processedData}
        backgroundColor="rgba(0,0,0,0)"
        nodeRelSize={6}
        nodeLabel={(node: any) => `${node.label}: ${node.name}`}
        onNodeClick={handleNodeClick}
        onLinkClick={handleLinkClick}
        onBackgroundClick={handleBackgroundClick}
        linkColor={(link: any) => link.color}
        linkDirectionalArrowLength={3}
        linkDirectionalArrowRelPos={1}
        nodeCanvasObject={(node: any, ctx, globalScale) => {
          const label = node.name;
          const fontSize = 12 / globalScale;
          const isSelected = node.id === selectedNodeId;
          
          ctx.font = `${fontSize}px Inter, sans-serif`;
          
          // Draw selection ring
          if (isSelected) {
            ctx.beginPath();
            ctx.arc(node.x, node.y, 6, 0, 2 * Math.PI, false);
            ctx.strokeStyle = '#60a5fa';
            ctx.lineWidth = 2 / globalScale;
            ctx.stroke();
          }

          // Draw circle
          ctx.beginPath();
          ctx.arc(node.x, node.y, 4, 0, 2 * Math.PI, false);
          ctx.fillStyle = node.color;
          ctx.fill();
          
          // Draw text
          if (globalScale > 0.8 || isSelected) {
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = isSelected ? '#ffffff' : 'rgba(255, 255, 255, 0.6)';
            ctx.fillText(label, node.x, node.y + 10);
          }
        }}
      />
    </div>
  );
};
