import { create } from 'zustand';
import type { TranscriptTurn, PipelineState, CallEndData } from '../types';

interface DemoCallState {
  sessionId: string | null;
  isActive: boolean;
  isConnecting: boolean;
  pipelineState: PipelineState;
  transcript: TranscriptTurn[];
  audioLevel: number;
  callDuration: number;
  error: string | null;

  // Audio
  mediaStream: MediaStream | null;
  audioContext: AudioContext | null;
  processor: ScriptProcessorNode | null;
  websocket: WebSocket | null;

  // Actions
  setConnecting: (connecting: boolean) => void;
  setActive: (active: boolean) => void;
  setSessionId: (id: string | null) => void;
  setPipelineState: (state: PipelineState) => void;
  addTranscript: (turn: TranscriptTurn) => void;
  setTranscript: (transcript: TranscriptTurn[]) => void;
  setAudioLevel: (level: number) => void;
  setCallDuration: (duration: number) => void;
  setError: (error: string | null) => void;
  setMediaStream: (stream: MediaStream | null) => void;
  setAudioContext: (ctx: AudioContext | null) => void;
  setProcessor: (proc: ScriptProcessorNode | null) => void;
  setWebSocket: (ws: WebSocket | null) => void;
  reset: () => void;
  handleCallEnd: (data: CallEndData) => void;
}

export const useDemoCallStore = create<DemoCallState>((set) => ({
  sessionId: null,
  isActive: false,
  isConnecting: false,
  pipelineState: 'idle',
  transcript: [],
  audioLevel: 0,
  callDuration: 0,
  error: null,

  mediaStream: null,
  audioContext: null,
  processor: null,
  websocket: null,

  setConnecting: (isConnecting) => set({ isConnecting }),
  setActive: (isActive) => set({ isActive }),
  setSessionId: (sessionId) => set({ sessionId }),
  setPipelineState: (pipelineState) => set({ pipelineState }),
  addTranscript: (turn) => set((state) => ({ transcript: [...state.transcript, turn] })),
  setTranscript: (transcript) => set({ transcript }),
  setAudioLevel: (audioLevel) => set({ audioLevel }),
  setCallDuration: (callDuration) => set({ callDuration }),
  setError: (error) => set({ error }),
  setMediaStream: (mediaStream) => set({ mediaStream }),
  setAudioContext: (audioContext) => set({ audioContext }),
  setProcessor: (processor) => set({ processor }),
  setWebSocket: (websocket) => set({ websocket }),
  reset: () =>
    set({
      sessionId: null,
      isActive: false,
      isConnecting: false,
      pipelineState: 'idle',
      transcript: [],
      audioLevel: 0,
      callDuration: 0,
      error: null,
      mediaStream: null,
      audioContext: null,
      processor: null,
      websocket: null,
    }),
  handleCallEnd: (data) =>
    set({
      isActive: false,
      isConnecting: false,
      pipelineState: 'ended',
      transcript: data.transcript,
      callDuration: data.duration,
      sessionId: null,
      mediaStream: null,
      audioContext: null,
      processor: null,
      websocket: null,
    }),
}));