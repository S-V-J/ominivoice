import { create } from 'zustand';
import type { Agent, AgentListResponse, AgentCompletenessResponse } from '../types';

interface AgentState {
  agents: AgentListResponse[];
  currentAgent: Agent | null;
  completeness: AgentCompletenessResponse | null;
  isLoading: boolean;

  setAgents: (agents: AgentListResponse[]) => void;
  addAgent: (agent: AgentListResponse) => void;
  updateAgent: (agentId: string, data: Partial<AgentListResponse>) => void;
  removeAgent: (agentId: string) => void;
  setCurrentAgent: (agent: Agent | null) => void;
  setCompleteness: (completeness: AgentCompletenessResponse | null) => void;
  setLoading: (loading: boolean) => void;
}

export const useAgentStore = create<AgentState>((set) => ({
  agents: [],
  currentAgent: null,
  completeness: null,
  isLoading: false,

  setAgents: (agents) => set({ agents }),
  addAgent: (agent) => set((state) => ({ agents: [agent, ...state.agents] })),
  updateAgent: (agentId, data) =>
    set((state) => ({
      agents: state.agents.map((a) => (a.id === agentId ? { ...a, ...data } : a)),
      currentAgent: state.currentAgent?.id === agentId ? { ...state.currentAgent, ...data } : state.currentAgent,
    })),
  removeAgent: (agentId) =>
    set((state) => ({
      agents: state.agents.filter((a) => a.id !== agentId),
      currentAgent: state.currentAgent?.id === agentId ? null : state.currentAgent,
    })),
  setCurrentAgent: (agent) => set({ currentAgent: agent }),
  setCompleteness: (completeness) => set({ completeness }),
  setLoading: (isLoading) => set({ isLoading }),
}));