import { useEffect, useRef } from 'react';
import { useProjectStore } from '../store/useProjectStore';
import { api } from '../lib/api';

export const useAgentSocket = (projectId: string | null) => {
  const socketRef = useRef<WebSocket | null>(null);
  const { updateStatus, addThought, setGraphData, setPendingApproval } = useProjectStore();

  const refreshProjectData = async () => {
    if (!projectId) return;
    try {
      const graph = await api.getProjectGraph(projectId);
      setGraphData(graph);
    } catch (err) {
      console.error('Refresh project data failed:', err);
    }
  };

  useEffect(() => {
    if (!projectId) return;

    // Initial load
    refreshProjectData();

    // Use absolute URL for the local FastAPI server
    const wsUrl = `ws://127.0.0.1:8000/ws/projects/${projectId}`;
    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      console.log('WebSocket Connected to project:', projectId);
    };

    socket.onmessage = async (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'status_update') {
          updateStatus(data.status, data.message);
          
          // Refresh graph on every status change
          refreshProjectData();

          // If paused, fetch approval details
          if (data.status === 'paused') {
            try {
              const approval = await api.getPendingApproval(projectId);
              setPendingApproval(approval);
            } catch (err) {
              console.error('Failed to fetch approval details:', err);
            }
          } else {
            setPendingApproval(null);
          }
        } else if (data.type === 'agent_thought') {
          addThought({
            agent: data.agent,
            thought: data.thought,
            timestamp: data.timestamp || new Date().toISOString()
          });
        }
      } catch (err) {
        console.error('Failed to parse socket message:', err);
      }
    };

    socket.onclose = () => {
      console.log('WebSocket Disconnected');
    };

    return () => {
      socket.close();
    };
  }, [projectId, updateStatus, addThought]);

  return socketRef.current;
};
