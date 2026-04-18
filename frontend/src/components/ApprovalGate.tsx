import React, { useState } from 'react';
import { useProjectStore } from '../store/useProjectStore';
import { api } from '../lib/api';
import { ShieldCheck, XCircle, CheckCircle, MessageSquare, Loader2 } from 'lucide-react';

export const ApprovalGate: React.FC = () => {
  const { projectId, pendingApproval, setPendingApproval, updateStatus } = useProjectStore();
  const [comment, setComment] = useState('');
  const [loading, setLoading] = useState(false);

  if (!pendingApproval || !projectId) return null;

  const handleDecision = async (approved: boolean) => {
    setLoading(true);
    try {
      await api.submitApproval(projectId, comment, approved);
      setPendingApproval(null);
      
      if (approved) {
        updateStatus('running_engineer', 'Architectural design approved by user. Proceeding to engineering.');
      } else {
        updateStatus('running_architect', 'Design rejected. Architect is iterating based on feedback.');
        // In reality, the backend would trigger the re-run, which we anticipate
      }
    } catch (err) {
      console.error('Approval submission failed:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-300">
      <div className="glass max-w-2xl w-full rounded-2xl p-8 shadow-2xl border-cyan-500/30 flex flex-col gap-6 scale-in-center">
        
        <div className="flex items-center gap-4">
          <div className="p-3 bg-cyan-500/20 rounded-xl text-cyan-400">
            <ShieldCheck size={32} />
          </div>
          <div>
            <h2 className="text-xl font-bold italic tracking-tight uppercase">Architectural Gate</h2>
            <p className="text-sm text-slate-400">The Architect has submitted a design for your review.</p>
          </div>
        </div>

        <div className="bg-black/40 rounded-xl p-6 border border-white/5 max-h-[400px] overflow-y-auto">
          <pre className="font-mono text-xs text-slate-300 whitespace-pre-wrap leading-relaxed">
            {typeof pendingApproval.content === 'string' 
              ? pendingApproval.content 
              : JSON.stringify(pendingApproval.content, null, 2)}
          </pre>
        </div>

        <div className="flex flex-col gap-3">
          <label className="text-[10px] uppercase font-bold tracking-widest text-slate-500 flex items-center gap-2">
            <MessageSquare size={12} /> Reviewer Comments
          </label>
          <textarea 
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Provide feedback or special instructions..."
            className="w-full bg-slate-900/50 border border-white/5 rounded-lg p-4 text-sm focus:outline-none focus:border-cyan-500/50 transition-colors resize-none h-24"
          />
        </div>

        <div className="flex gap-4">
          <button
            onClick={() => handleDecision(true)}
            disabled={loading}
            className="flex-1 h-12 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 rounded-xl font-bold flex items-center justify-center gap-2 transition-all shadow-lg shadow-cyan-900/40"
          >
            {loading ? <Loader2 className="animate-spin" /> : <><CheckCircle size={18} /> Approve Design</>}
          </button>
          
          <button
            onClick={() => handleDecision(false)}
            disabled={loading}
            className="px-6 h-12 bg-slate-900 hover:bg-rose-950/30 border border-white/5 hover:border-rose-500/50 rounded-xl font-bold flex items-center justify-center gap-2 transition-all group"
          >
            <XCircle size={18} className="text-slate-500 group-hover:text-rose-500" />
            <span className="text-slate-400 group-hover:text-rose-400 text-sm">Reject</span>
          </button>
        </div>

      </div>
    </div>
  );
};
