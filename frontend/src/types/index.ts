/** Type definitions for OminiVoice frontend */

export type UserPlan = 'free' | 'starter' | 'pro' | 'enterprise';
export type AgentDirection = 'inbound' | 'outbound';
export type AgentStatus = 'draft' | 'active' | 'paused' | 'archived';
export type InterruptionSensitivity = 'low' | 'medium' | 'high';
export type STTEngine = 'faster-whisper' | 'riva-asr';
export type TTSEngine = 'kokoro' | 'piper' | 'chatterbox';
export type LLMProvider = 'nvidia_integrate';
export type VoiceStack = 'stack_a' | 'stack_b';

export interface User {
  id: string;
  email: string;
  plan: UserPlan;
  stripe_customer_id: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface Agent {
  id: string;
  owner_id: string;
  name: string;
  direction: AgentDirection;
  status: AgentStatus;
  // Voice stack selection
  voice_stack: VoiceStack;
  // Stack A (Local) engines
  stt_engine: STTEngine;
  tts_engine: TTSEngine;
  tts_voice: string;
  language: string;
  // Stack B (NVIDIA NIM) engines
  chatterbox_voice: string;
  chatterbox_emotion_exaggeration: number;
  riva_asr_language: string;
  riva_vad_threshold: number;
  llm_provider: LLMProvider;
  llm_model: string;
  system_prompt: string | null;
  interruption_sensitivity: InterruptionSensitivity;
  max_call_duration_s: number;
  silence_timeout_s: number;
  opening_line: string | null;
  objective_prompt: string | null;
  objection_handling_prompt: string | null;
  voicemail_prompt: string | null;
  closing_prompt: string | null;
  escalation_rule: string | null;
  greeting_prompt: string | null;
  qualification_prompt: string | null;
  knowledge_prompt: string | null;
  fallback_prompt: string | null;
  handoff_prompt: string | null;
  created_at: string;
  updated_at: string;
  completeness_percentage?: number;
}

export interface AgentListResponse {
  id: string;
  name: string;
  direction: AgentDirection;
  status: AgentStatus;
  completeness_percentage: number;
  last_test_call_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentCompletenessResponse {
  agent_id: string;
  direction: AgentDirection;
  is_complete: boolean;
  missing_required_fields: string[];
  field_status: Record<string, boolean>;
  completion_percentage: number;
}

export interface AgentPromptVersion {
  id: string;
  agent_id: string;
  field_name: string;
  old_value: string | null;
  new_value: string | null;
  edited_at: string;
}

export interface APIKey {
  id: string;
  agent_id: string;
  user_id: string;
  key_hash: string;
  key_prefix: string;
  webhook_url: string;
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
}

export interface CallLog {
  id: string;
  agent_id: string;
  direction: AgentDirection;
  caller_ref: string | null;
  transcript: TranscriptTurn[] | null;
  duration_s: number;
  status: string;
  started_at: string;
  ended_at: string | null;
  error_message: string | null;
  call_metadata: Record<string, unknown> | null;
}

export interface TranscriptTurn {
  turn_id: number;
  role: 'user' | 'assistant';
  text: string;
  timestamp: string;
  duration_ms: number;
  interrupted: boolean;
}

export type QueueEntryStatus = 'pending' | 'queued' | 'in_progress' | 'completed' | 'failed';

export interface ColdCallQueueEntry {
  id: string;
  agent_id: string;
  contact_name: string;
  phone_number: string;
  source: string | null;
  status: QueueEntryStatus;
  payload: Record<string, unknown> | null;
  scheduled_at: string | null;
  attempts: number;
  last_attempt_at: string | null;
  error_message: string | null;
  call_log_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ColdCallQueueStats {
  agent_id: string;
  total: number;
  pending: number;
  queued: number;
  in_progress: number;
  completed: number;
  failed: number;
}

export interface CallLogStats {
  total_calls: number;
  completed: number;
  failed: number;
  inbound: number;
  outbound: number;
  total_duration_seconds: number;
  average_duration_seconds: number;
  success_rate: number;
}

export interface RewritePromptResponse {
  field_name: string;
  original: string;
  rewritten: string;
}

// Auth types
export interface RegisterRequest {
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface RefreshRequest {
  refresh_token: string;
}

// Demo call types
export interface StartCallRequest {
  agent_id: string;
  direction: AgentDirection;
  system_prompt: string;
  opening_line: string;
  objective_prompt: string;
  objection_handling_prompt: string;
  voicemail_prompt: string;
  closing_prompt: string;
  escalation_rule: string;
  greeting_prompt: string;
  qualification_prompt: string;
  knowledge_prompt: string;
  fallback_prompt: string;
  handoff_prompt: string;
  interruption_sensitivity: InterruptionSensitivity;
  max_call_duration_s: number;
  silence_timeout_s: number;
  language: string;
  stt_engine: STTEngine;
  tts_engine: TTSEngine;
  tts_voice: string;
  llm_provider: LLMProvider;
  llm_model: string;
  // Stack B fields
  voice_stack: VoiceStack;
  chatterbox_voice: string;
  chatterbox_emotion_exaggeration: number;
  riva_asr_language: string;
  riva_vad_threshold: number;
}

export interface StartCallResponse {
  session_id: string;
  ws_url: string;
  agent_id: string;
  direction: AgentDirection;
  status: string;
}

export interface WebSocketMessage {
  type: 'transcript' | 'state' | 'end';
  data: TranscriptTurn | string | CallEndData;
}

export interface CallEndData {
  session_id: string;
  transcript: TranscriptTurn[];
  duration: number;
}

export type PipelineState = 'idle' | 'initializing' | 'listening' | 'processing' | 'speaking' | 'ended' | 'error';