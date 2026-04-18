import { create } from 'zustand';
import { api } from '../lib/api';

export type AgentType = 'ProductManager' | 'Architect' | 'Engineer' | 'CodeReview' | 'Reflexion' | 'DevOps';

export interface AgentThought {
  agent: AgentType;
  thought: string;
  timestamp: string;
}

export interface GraphData {
  nodes: any[];
  links: any[];
}

export interface ApprovalRequest {
  id: string;
  stage: string;
  status: string;
  content: any;
}

export interface ProjectState {
  projectId: string | null;
  status: string;
  messages: string[];
  thoughts: AgentThought[];
  graphData: GraphData;
  pendingApproval: ApprovalRequest | null;
  selectedNodeId: string | null;
  selectedLinkId: string | null;
  projectList: any[];
  setProjectId: (id: string) => void;
  updateStatus: (status: string, message?: string) => void;
  addThought: (thought: AgentThought) => void;
  setGraphData: (data: GraphData) => void;
  setPendingApproval: (approval: ApprovalRequest | null) => void;
  setSelectedNodeId: (id: string | null) => void;
  setSelectedLinkId: (id: string | null) => void;
  fetchProjects: () => Promise<void>;
  reset: () => void;
}

export const useProjectStore = create<ProjectState>((set) => ({
  projectId: null,
  status: 'idle',
  messages: [],
  thoughts: [],
  graphData: { nodes: [], links: [] },
  pendingApproval: null,
  selectedNodeId: null,
  selectedLinkId: null,
  setProjectId: (id) => set({ 
    projectId: id, 
    messages: [], 
    thoughts: [], 
    status: 'initializing', 
    graphData: { nodes: [], links: [] }, 
    pendingApproval: null,
    selectedNodeId: null,
    selectedLinkId: null
  }),
  updateStatus: (status, message) => set((state) => ({ 
    status, 
    messages: message ? [...state.messages, message] : state.messages 
  })),
  addThought: (thought) => set((state) => ({ 
    thoughts: [thought, ...state.thoughts].slice(0, 50) 
  })),
  setGraphData: (data) => set({ graphData: data }),
  setPendingApproval: (approval) => set({ pendingApproval: approval }),
  setSelectedNodeId: (id) => set({ selectedNodeId: id, selectedLinkId: null }),
  setSelectedLinkId: (id) => set({ selectedLinkId: id, selectedNodeId: null }),
  projectList: [],
  fetchProjects: async () => {
    try {
      const data = await api.listProjects();
      set({ projectList: data });
    } catch (error) {
      console.error('Failed to fetch projects:', error);
    }
  },
  reset: () => set({ 
    projectId: null, 
    status: 'idle', 
    messages: [], 
    thoughts: [], 
    graphData: { nodes: [], links: [] }, 
    pendingApproval: null,
    selectedNodeId: null,
    selectedLinkId: null 
  }),
}));
