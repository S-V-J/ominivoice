import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAgentStore } from '../store/agentStore';
import { useDemoCall } from '../hooks/useDemoCall';
import { api } from '../services/api';
import toast from 'react-hot-toast';
import type { Agent, AgentDirection } from '../types';
import QueueTab from '../components/QueueTab';
import CallLogsTab from '../components/CallLogsTab';
import {
  ArrowLeftIcon,
  TrashIcon,
  MicrophoneIcon,
  PhoneArrowUpRightIcon,
  PhoneArrowDownLeftIcon,
  Cog6ToothIcon,
  DocumentTextIcon,
  PlayIcon,
  StopIcon,
  XMarkIcon,
  ListBulletIcon,
  PhoneIcon,
  KeyIcon,
  ClipboardDocumentIcon,
} from '@heroicons/react/24/outline';
import PromptVersionsTab from '../components/PromptVersionsTab';

const PROMPT_FIELDS: Record<AgentDirection, { key: keyof Agent; label: string; description: string }[]> = {
  outbound: [
    { key: 'system_prompt', label: 'System Prompt (Persona)', description: 'Persona, tone, do\'s/don\'ts for the agent' },
    { key: 'opening_line', label: 'Opening Line', description: 'First thing said when the callee picks up' },
    { key: 'objective_prompt', label: 'Objective', description: 'What the call is trying to achieve (book meeting, confirm order, etc.)' },
    { key: 'objection_handling_prompt', label: 'Objection Handling', description: 'How to respond to pushback / "not interested"' },
    { key: 'voicemail_prompt', label: 'Voicemail Message', description: 'What to say if voicemail/no-answer is detected' },
    { key: 'closing_prompt', label: 'Closing', description: 'How to end the call / next steps' },
    { key: 'escalation_rule', label: 'Escalation Rule', description: 'When to say "let me transfer you to a human"' },
  ],
  inbound: [
    { key: 'system_prompt', label: 'System Prompt (Persona)', description: 'Persona, tone, do\'s/don\'ts for the agent' },
    { key: 'greeting_prompt', label: 'Greeting', description: 'First thing said when a call is answered' },
    { key: 'qualification_prompt', label: 'Qualification', description: 'Questions to ask to route/understand caller intent' },
    { key: 'knowledge_prompt', label: 'Knowledge Base', description: 'FAQ / product info the agent should ground answers in' },
    { key: 'fallback_prompt', label: 'Fallback', description: 'What to say when the agent doesn\'t know the answer' },
    { key: 'handoff_prompt', label: 'Handoff', description: 'How to hand off to a human/ticket' },
  ],
};

const SHARED_FIELDS: { key: keyof Agent; label: string; type: 'text' | 'select' | 'number'; options?: string[] }[] = [
  { key: 'voice_stack', label: 'Voice Technology Stack', type: 'select', options: ['stack_a', 'stack_b'] },
  { key: 'interruption_sensitivity', label: 'Interruption Sensitivity', type: 'select', options: ['low', 'medium', 'high'] },
  { key: 'max_call_duration_s', label: 'Max Call Duration (seconds)', type: 'number' },
  { key: 'silence_timeout_s', label: 'Silence Timeout (seconds)', type: 'number' },
  { key: 'language', label: 'Language', type: 'text' },
  // Stack A (Local) engines
  { key: 'stt_engine', label: 'STT Engine (Stack A)', type: 'select', options: ['faster-whisper'] },
  { key: 'tts_engine', label: 'TTS Engine (Stack A)', type: 'select', options: ['kokoro', 'piper'] },
  { key: 'tts_voice', label: 'TTS Voice (Stack A)', type: 'text' },
  // Stack B (NVIDIA NIM) engines
  { key: 'chatterbox_voice', label: 'Chatterbox Voice (Stack B)', type: 'text' },
  { key: 'chatterbox_emotion_exaggeration', label: 'Chatterbox Emotion (0-1)', type: 'text' },
  { key: 'riva_asr_language', label: 'Riva ASR Language (Stack B)', type: 'text' },
  { key: 'riva_vad_threshold', label: 'Riva VAD Threshold (0-1)', type: 'text' },
  { key: 'llm_provider', label: 'LLM Provider', type: 'select', options: ['nvidia_integrate'] },
  { key: 'llm_model', label: 'LLM Model', type: 'text' },
];

export default function AgentDetail() {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();
  const { currentAgent, setCurrentAgent, setCompleteness, setLoading, removeAgent } = useAgentStore();
  const { startCall, endCall, isActive, isConnecting, pipelineState, transcript, audioLevel, callDuration, error } = useDemoCall();
  const [activeTab, setActiveTab] = useState<'configure' | 'test' | 'queue' | 'calls' | 'api' | 'versions'>('configure');
  const [isSaving, setIsSaving] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [editedValues, setEditedValues] = useState<Record<string, any>>({});

  useEffect(() => {
    if (agentId) {
      loadAgent();
      loadCompleteness();
    }
  }, [agentId]);

  const loadAgent = async () => {
    setLoading(true);
    try {
      const agent = await api.getAgent(agentId!);
      setCurrentAgent(agent);
      // Initialize edited values
      const initialValues: Record<string, any> = {};
      const promptFields = PROMPT_FIELDS[agent.direction as AgentDirection];
      promptFields.forEach((f: { key: keyof Agent; label: string; description: string }) => { initialValues[f.key] = agent[f.key] || ''; });
      SHARED_FIELDS.forEach((f: { key: keyof Agent; label: string; type: 'text' | 'select' | 'number'; options?: string[] }) => { initialValues[f.key] = agent[f.key]; });
      setEditedValues(initialValues);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to load agent');
      navigate('/dashboard');
    } finally {
      setLoading(false);
    }
  };

  const loadCompleteness = async () => {
    try {
      const completeness = await api.getAgentCompleteness(agentId!);
      setCompleteness(completeness);
    } catch (err) {
      console.error('Failed to load completeness:', err);
    }
  };

  const handleSave = async () => {
    if (!currentAgent) return;
    setIsSaving(true);
    try {
      await api.updateAgent(currentAgent.id, editedValues);
      toast.success('Agent saved');
      loadAgent();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save agent');
    } finally {
      setIsSaving(false);
    }
  };

  const handleFieldChange = (field: string, value: any) => {
    setEditedValues(prev => ({ ...prev, [field]: value }));
  };

  const handleTestCall = async () => {
    if (!currentAgent) return;
    await startCall(currentAgent);
  };

  const handleEndCall = async () => {
    await endCall();
  };

  const getDirectionLabel = (direction: AgentDirection) => {
    return direction === 'outbound' ? 'Outbound (Call Out)' : 'Inbound (Call In)';
  };

  const getDirectionIcon = (direction: AgentDirection) => {
    return direction === 'outbound' ? <PhoneArrowUpRightIcon className="w-5 h-5" /> : <PhoneArrowDownLeftIcon className="w-5 h-5" />;
  };

  const getStatusBadge = (status: string) => {
    const badges: Record<string, string> = {
      draft: 'badge-gray',
      active: 'badge-success',
      paused: 'badge-warning',
      archived: 'badge-info',
    };
    return badges[status] || 'badge-gray';
  };

  if (!currentAgent) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary-600 border-t-transparent"></div>
      </div>
    );
  }

  const promptFields = PROMPT_FIELDS[currentAgent.direction];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <button onClick={() => navigate('/dashboard')} className="text-gray-500 hover:text-gray-700">
            <ArrowLeftIcon className="w-6 h-6" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{currentAgent.name}</h1>
            <div className="flex items-center space-x-3 mt-1">
              <span className={`badge ${getStatusBadge(currentAgent.status)}`}>{currentAgent.status}</span>
              <span className="badge badge-info flex items-center">
                {getDirectionIcon(currentAgent.direction)}
                <span className="ml-1">{getDirectionLabel(currentAgent.direction)}</span>
              </span>
              <span className="badge badge-gray flex items-center">
                <DocumentTextIcon className="w-4 h-4 mr-1" />
                {currentAgent.completeness_percentage || 0}% complete
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <button onClick={() => setShowDeleteConfirm(true)} className="btn-ghost text-red-600 hover:bg-red-50">
            <TrashIcon className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8" aria-label="Tabs">
          {[
            { id: 'configure', label: 'Configure', icon: Cog6ToothIcon },
            { id: 'test', label: 'Test Agent', icon: MicrophoneIcon },
            { id: 'queue', label: 'Cold Call Queue', icon: ListBulletIcon },
            { id: 'calls', label: 'Call Logs', icon: PhoneIcon },
            { id: 'api', label: 'API & Webhook', icon: DocumentTextIcon },
            { id: 'versions', label: 'Prompt History', icon: DocumentTextIcon },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === tab.id
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <tab.icon className="w-5 h-5" />
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'configure' && (
        <div className="space-y-6">
          {/* Prompt Fields */}
          <div className="card">
            <div className="card-header">
              <h2 className="text-lg font-semibold text-gray-900">Prompt Configuration</h2>
              <p className="text-sm text-gray-500 mt-1">
                Required fields for {getDirectionLabel(currentAgent.direction).toLowerCase()} agents are marked with *
              </p>
            </div>
            <div className="card-body space-y-6">
              {promptFields.map((field) => (
                <PromptEditor
                  key={field.key}
                  label={field.label}
                  description={field.description}
                  value={editedValues[field.key] || ''}
                  onChange={(v) => handleFieldChange(field.key, v)}
                  required={true}
                />
              ))}
            </div>
          </div>

          {/* Shared Configuration */}
          <div className="card">
            <div className="card-header">
              <h2 className="text-lg font-semibold text-gray-900">Shared Configuration</h2>
            </div>
            <div className="card-body space-y-4">
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {SHARED_FIELDS.map((field) => (
                  <ConfigField
                    key={field.key}
                    label={field.label}
                    type={field.type}
                    value={editedValues[field.key]}
                    onChange={(v) => handleFieldChange(field.key, v)}
                    options={field.options}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* Save Button */}
          <div className="flex justify-end">
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="btn-primary"
            >
              {isSaving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </div>
      )}

      {activeTab === 'test' && (
        <TestCallTab
          agent={currentAgent}
          isActive={isActive}
          isConnecting={isConnecting}
          pipelineState={pipelineState}
          transcript={transcript}
          audioLevel={audioLevel}
          callDuration={callDuration}
          error={error}
          onStartCall={handleTestCall}
          onEndCall={handleEndCall}
        />
      )}

      {activeTab === 'queue' && (
        <QueueTab agent={currentAgent} />
      )}

      {activeTab === 'calls' && (
        <CallLogsTab agent={currentAgent} />
      )}

      {activeTab === 'api' && (
        <ApiKeyTab agentId={currentAgent.id} />
      )}

      {activeTab === 'versions' && (
        <PromptVersionsTab agentId={currentAgent.id} />
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-md mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Delete Agent</h3>
            <p className="text-gray-600 mb-6">
              Are you sure you want to delete "{currentAgent.name}"? This will also delete all API keys, call logs, and prompt history. This action cannot be undone.
            </p>
            <div className="flex justify-end space-x-3">
              <button onClick={() => setShowDeleteConfirm(false)} className="btn-secondary">
                Cancel
              </button>
              <button
                onClick={async () => {
                  try {
                    await api.deleteAgent(currentAgent.id);
                    removeAgent(currentAgent.id);
                    toast.success('Agent deleted');
                    navigate('/dashboard');
                  } catch (err: any) {
                    toast.error(err.response?.data?.detail || 'Failed to delete agent');
                  }
                }}
                className="btn-danger"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function PromptEditor({
  label,
  description,
  value,
  onChange,
  required,
}: {
  label: string;
  description: string;
  value: string;
  onChange: (v: string) => void;
  required: boolean;
}) {
  const [showRewrite, setShowRewrite] = useState(false);
  const [rewrittenText, setRewrittenText] = useState('');
  const [isRewriting, setIsRewriting] = useState(false);

  // We need to get the agent ID from context - use the current agent in the store
  // Since we're in AgentDetail, we can access it via the store
  const { currentAgent } = useAgentStore();

  const handleRewrite = async () => {
    if (!currentAgent) return;

    setIsRewriting(true);
    try {
      const response = await api.rewritePrompt(currentAgent.id, label, value);
      setRewrittenText(response.rewritten);
      setShowRewrite(true);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to rewrite prompt');
    } finally {
      setIsRewriting(false);
    }
  };

  const applyRewrite = () => {
    onChange(rewrittenText);
    setShowRewrite(false);
    setRewrittenText('');
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="label">
          {label} {required && <span className="text-red-500">*</span>}
        </label>
        <button
          onClick={handleRewrite}
          disabled={isRewriting || !value.trim()}
          className="btn-ghost text-xs"
        >
          {isRewriting ? 'Rewriting...' : '✨ Rewrite with AI'}
        </button>
      </div>
      <p className="text-xs text-gray-500">{description}</p>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="input min-h-[100px] font-mono text-sm"
        rows={4}
        placeholder={`Enter ${label.toLowerCase()}...`}
      />
      {showRewrite && (
        <div className="border border-primary-200 bg-primary-50 rounded-lg p-4 space-y-3">
          <div>
            <p className="text-sm font-medium text-gray-900 mb-1">AI Suggestion</p>
            <textarea
              value={rewrittenText}
              onChange={(e) => setRewrittenText(e.target.value)}
              className="input min-h-[80px] font-mono text-sm"
              rows={3}
            />
          </div>
          <div className="flex justify-end space-x-2">
            <button onClick={() => setShowRewrite(false)} className="btn-secondary text-sm">
              Discard
            </button>
            <button onClick={applyRewrite} className="btn-primary text-sm">
              Accept
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function ConfigField({
  label,
  type,
  value,
  onChange,
  options,
}: {
  label: string;
  type: 'text' | 'select' | 'number';
  value: any;
  onChange: (v: any) => void;
  options?: string[];
}) {
  if (type === 'select' && options) {
    return (
      <div>
        <label className="label">{label}</label>
        <select
          value={value || ''}
          onChange={(e) => onChange(e.target.value)}
          className="input"
        >
          {options.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      </div>
    );
  }

  if (type === 'number') {
    return (
      <div>
        <label className="label">{label}</label>
        <input
          type="number"
          value={value || ''}
          onChange={(e) => onChange(parseInt(e.target.value) || 0)}
          className="input"
        />
      </div>
    );
  }

  return (
    <div>
      <label className="label">{label}</label>
      <input
        type="text"
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        className="input"
      />
    </div>
  );
}

function TestCallTab({
  agent: _agent,
  isActive,
  isConnecting,
  pipelineState,
  transcript,
  audioLevel,
  callDuration,
  error,
  onStartCall,
  onEndCall,
}: {
  agent: Agent;
  isActive: boolean;
  isConnecting: boolean;
  pipelineState: string;
  transcript: any[];
  audioLevel: number;
  callDuration: number;
  error: string | null;
  onStartCall: () => void;
  onEndCall: () => void;
}) {
  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getPipelineStateColor = (state: string) => {
    const colors: Record<string, string> = {
      idle: 'text-gray-500',
      initializing: 'text-blue-500',
      listening: 'text-green-500',
      processing: 'text-yellow-500',
      speaking: 'text-purple-500',
      ended: 'text-gray-500',
      error: 'text-red-500',
    };
    return colors[state] || 'text-gray-500';
  };

  return (
    <div className="space-y-6">
      <div className="card">
        <div className="card-header">
          <h2 className="text-lg font-semibold text-gray-900">Simulated Call Test</h2>
          <p className="text-sm text-gray-500 mt-1">
            This is a simulated test call in your browser — no real phone call is placed.
            Uses WebRTC for real-time audio streaming.
          </p>
        </div>
        <div className="card-body space-y-6">
          {/* Status & Controls */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <div className={`w-3 h-3 rounded-full ${
                  isConnecting ? 'bg-yellow-500 animate-pulse' :
                  isActive ? 'bg-green-500' : 'bg-gray-300'
                }`}></div>
                <span className={`font-medium ${isActive ? 'text-green-700' : isConnecting ? 'text-yellow-700' : 'text-gray-700'}`}>
                  {isConnecting ? 'Connecting...' : isActive ? 'Call Active' : 'Ready'}
                </span>
                {isActive && (
                  <span className={`text-sm px-2 py-1 rounded ${getPipelineStateColor(pipelineState)} font-medium capitalize`}>
                    {pipelineState}
                  </span>
                )}
              </div>
              <div className="flex items-center space-x-2">
                {isActive && (
                  <>
                    <div className="flex items-center space-x-2 text-sm text-gray-600">
                      <span>Duration:</span>
                      <span className="font-mono font-medium">{formatDuration(callDuration)}</span>
                    </div>
                    <div className="w-32 h-2 bg-gray-200 rounded overflow-hidden">
                      <div
                        className="h-full bg-green-500 transition-all duration-100"
                        style={{ width: `${Math.min(100, audioLevel)}%` }}
                      ></div>
                    </div>
                  </>
                )}
              </div>
            </div>

            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                {error}
              </div>
            )}

            <div className="flex space-x-3">
              {!isActive && !isConnecting ? (
                <button
                  onClick={onStartCall}
                  disabled={isConnecting}
                  className="btn-primary flex-1 lg:flex-none"
                >
                  <PlayIcon className="w-5 h-5 mr-2" />
                  Start Test Call
                </button>
              ) : (
                <button
                  onClick={onEndCall}
                  className="btn-danger flex-1 lg:flex-none"
                >
                  <StopIcon className="w-5 h-5 mr-2" />
                  End Call
                </button>
              )}
            </div>
          </div>

          {/* Transcript */}
          <div>
            <h3 className="text-sm font-medium text-gray-900 mb-3">Live Transcript</h3>
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 max-h-96 overflow-y-auto scrollbar-thin">
              {transcript.length === 0 ? (
                <p className="text-gray-500 text-center py-8">
                  {isActive ? 'Listening...' : 'Transcript will appear here during the call'}
                </p>
              ) : (
                <div className="space-y-3">
                  {transcript.map((turn, idx) => (
                    <div key={idx} className="flex flex-col space-y-1">
                      <div className="flex items-baseline space-x-2">
                        <span className={`font-medium text-sm ${turn.role === 'assistant' ? 'text-green-700' : 'text-blue-700'}`}>
                          {turn.role === 'assistant' ? 'Agent' : 'You'}
                        </span>
                        <span className="text-xs text-gray-500">
                          {new Date(turn.timestamp).toLocaleTimeString()}
                        </span>
                        {turn.interrupted && (
                          <span className="text-xs text-red-600 bg-red-50 px-1.5 py-0.5 rounded">INTERRUPTED</span>
                        )}
                      </div>
                      <p className="text-gray-800 ml-6">{turn.text}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Call Summary (shown after call ends) */}
      {!isActive && transcript.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h2 className="text-lg font-semibold text-gray-900">Call Summary</h2>
          </div>
          <div className="card-body">
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="text-2xl font-bold text-gray-900">{formatDuration(callDuration)}</p>
                <p className="text-sm text-gray-500">Duration</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">{transcript.length}</p>
                <p className="text-sm text-gray-500">Turns</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">
                  {transcript.filter(t => t.interrupted).length}
                </p>
                <p className="text-sm text-gray-500">Interruptions</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ApiKeyTab({ agentId }: { agentId: string }) {
  const [apiKey, setApiKey] = useState<any>(null);
  const [showKey, setShowKey] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [webhookUrl, setWebhookUrl] = useState('');
  const [isUpdatingWebhook, setIsUpdatingWebhook] = useState(false);
  const [newKey, setNewKey] = useState('');

  useEffect(() => {
    loadApiKey();
  }, [agentId]);

  const loadApiKey = async () => {
    try {
      const data = await api.getApiKey(agentId);
      setApiKey(data);
      setWebhookUrl(data.webhook_url || '');
    } catch (err: any) {
      if (err.response?.status !== 404) {
        toast.error('Failed to load API key');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegenerate = async () => {
    if (!confirm('This will invalidate the current API key immediately. Continue?')) return;
    try {
      const data = await api.regenerateApiKey(agentId);
      setApiKey(data);
      setNewKey(data.key);
      setShowKey(true);
      toast.success('API key regenerated');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to regenerate key');
    }
  };

  const handleRevoke = async () => {
    if (!confirm('Revoke the API key? This cannot be undone.')) return;
    try {
      await api.revokeApiKey(agentId);
      setApiKey(null);
      toast.success('API key revoked');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to revoke key');
    }
  };

  const handleUpdateWebhook = async () => {
    setIsUpdatingWebhook(true);
    try {
      await api.updateWebhookUrl(agentId, webhookUrl);
      toast.success('Webhook URL updated');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update webhook');
    } finally {
      setIsUpdatingWebhook(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
  };

  if (isLoading) {
    return (
      <div className="card card-body flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-4 border-primary-600 border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {newKey && (
        <div className="card border-green-200 bg-green-50">
          <div className="card-body">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-semibold text-green-800">New API Key Generated</h3>
              <button onClick={() => setNewKey('')} className="text-green-600 hover:text-green-800">
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>
            <p className="text-sm text-green-700 mb-3">Save this key now — it won't be shown again.</p>
            <div className="flex space-x-2">
              <input
                type="text"
                value={newKey}
                readOnly
                className="input flex-1 font-mono text-sm"
              />
              <button onClick={() => copyToClipboard(newKey)} className="btn-secondary">
                Copy
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-header flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">API Key</h2>
          {!apiKey && (
            <button onClick={handleRegenerate} className="btn-primary">
              Generate API Key
            </button>
          )}
          {apiKey && (
            <button onClick={handleRegenerate} className="btn-secondary">
              Regenerate Key
            </button>
          )}
        </div>
        <div className="card-body space-y-4">
          {apiKey ? (
            <>
              <div>
                <label className="label">API Key</label>
                <div className="flex space-x-2">
                  <input
                    type={showKey ? 'text' : 'password'}
                    value={apiKey.key_prefix + '••••••••••••••••••••••'}
                    readOnly
                    className="input flex-1 font-mono"
                  />
                  <button onClick={() => setShowKey(!showKey)} className="btn-secondary">
                    {showKey ? 'Hide' : 'Show'}
                  </button>
                  <button onClick={() => copyToClipboard(apiKey.key_prefix + '••••••••••••••••••••••')} className="btn-secondary">
                    Copy Prefix
                  </button>
                </div>
                <p className="text-xs text-gray-500 mt-1">Full key only shown once on generation</p>
              </div>

              <div>
                <label className="label">Webhook URL</label>
                <div className="flex space-x-2">
                  <input
                    type="url"
                    value={webhookUrl}
                    onChange={(e) => setWebhookUrl(e.target.value)}
                    className="input flex-1"
                    placeholder="https://your-app.com/webhook/agent/..."
                  />
                  <button
                    onClick={handleUpdateWebhook}
                    disabled={isUpdatingWebhook}
                    className="btn-primary"
                  >
                    {isUpdatingWebhook ? 'Saving...' : 'Save'}
                  </button>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  POST requests with call events will be sent to this URL
                </p>
              </div>

              <div className="pt-4 border-t border-gray-200">
                <button
                  onClick={handleRevoke}
                  className="btn-danger"
                >
                  Revoke API Key
                </button>
              </div>
            </>
          ) : (
            <p className="text-gray-500 text-center py-8">
              No API key generated yet. Click "Generate API Key" to create one.
            </p>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h2 className="text-lg font-semibold text-gray-900">Usage</h2>
        </div>
        <div className="card-body">
          <pre className="bg-gray-100 rounded-lg p-4 text-sm overflow-x-auto text-gray-800">
{`# Authentication Header
Authorization: Bearer ${apiKey?.key_prefix}••••••••••••••••••••••

# Example webhook payload (POST to your webhook URL)
{
  "event": "call.started",
  "agent_id": "${agentId}",
  "call_id": "uuid",
  "timestamp": "2026-01-15T10:30:00Z",
  "direction": "outbound",
  "caller_ref": "+15551234567"
}`}
          </pre>
        </div>
      </div>

      {/* Universal Voice Agent WebSocket - Complete Documentation */}
      {apiKey && (
        <div className="card">
          <div className="card-header flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Universal Voice Agent WebSocket</h2>
            <span className="badge badge-success">Production Ready - Zero Portal Config</span>
          </div>
          <div className="card-body space-y-6">
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-2">
                <span className="text-lg">✅</span>
                <h3 className="font-semibold text-green-800">Universal Voice Agent WebSocket - Complete</h3>
              </div>
              <p className="text-green-700 text-sm">
                Connect ANY telephony system (Asterisk, FreeSWITCH, OpenSIPS, Twilio, custom SIP) with full configuration passed at connection time — NO portal setup required.
              </p>
            </div>

            {/* Endpoint URLs */}
            <div className="bg-gray-50 rounded-lg p-4">
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center space-x-2">
                <span className="text-lg">🔗</span> WebSocket Endpoints
              </h3>
              <div className="space-y-3 text-sm">
                <div>
                  <label className="label">Local (LAN) - wss://ominivoice.local/ws</label>
                  <div className="flex space-x-1">
                    <input
                      type="text"
                      value="wss://ominivoice.local/ws?api_key=YOUR_API_KEY"
                      readOnly
                      className="input flex-1 font-mono text-xs bg-gray-100"
                    />
                    <button
                      onClick={() => copyToClipboard("wss://ominivoice.local/ws?api_key=")}
                      className="btn-secondary text-xs"
                      title="Copy URL"
                    >
                      <ClipboardDocumentIcon className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                <div>
                  <label className="label">Internet (AWS) - wss://api.ominivoice.com/ws</label>
                  <div className="flex space-x-1">
                    <input
                      type="text"
                      value="wss://api.ominivoice.com/ws?api_key=YOUR_API_KEY"
                      readOnly
                      className="input flex-1 font-mono text-xs bg-gray-100"
                    />
                    <button
                      onClick={() => copyToClipboard("wss://api.ominivoice.com/ws?api_key=")}
                      className="btn-secondary text-xs"
                      title="Copy URL"
                    >
                      <ClipboardDocumentIcon className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
              <p className="text-xs text-gray-500 mt-2">
                Single universal endpoint for ALL agents — the API key or test token authenticates and the <code>config</code> message provides full agent configuration.
              </p>
            </div>

            {/* Supported Systems */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h3 className="font-semibold text-blue-800 mb-3 flex items-center space-x-2">
                <span className="text-lg">📞</span> Supported Telephony Systems
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm text-blue-700">
                <span className="flex items-center space-x-1"><span>✅</span><span>Asterisk</span></span>
                <span className="flex items-center space-x-1"><span>✅</span><span>FreeSWITCH</span></span>
                <span className="flex items-center space-x-1"><span>✅</span><span>OpenSIPS</span></span>
                <span className="flex items-center space-x-1"><span>✅</span><span>Twilio</span></span>
                <span className="flex items-center space-x-1"><span>✅</span><span>Custom SIP</span></span>
                <span className="flex items-center space-x-1"><span>✅</span><span>WebRTC</span></span>
                <span className="flex items-center space-x-1"><span>✅</span><span>Any VoIP</span></span>
              </div>
            </div>

            {/* Authentication Methods */}
            <div className="space-y-4">
              <h3 className="font-semibold text-gray-900">Authentication (Choose One)</h3>

              <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
                <div className="flex items-center space-x-2 mb-2">
                  <KeyIcon className="w-5 h-5 text-gray-600" />
                  <h4 className="font-semibold text-gray-900">API Key Authentication</h4>
                </div>
                <div className="space-y-2 text-sm">
                  <p className="text-gray-600">For production integrations. Full config required in first message.</p>
                  <div className="font-mono text-xs bg-gray-100 p-2 rounded">
                    wss://ominivoice.local/ws?api_key=${agentId}
                  </div>
                  <p className="text-gray-500">Requires <code>agent_id</code> in <code>config</code> message for tracking.</p>
                </div>
              </div>

              <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
                <div className="flex items-center space-x-2 mb-2">
                  <KeyIcon className="w-5 h-5 text-green-600" />
                  <h4 className="font-semibold text-gray-900">Test Token (1-Hour JWT)</h4>
                </div>
                <div className="space-y-2 text-sm">
                  <p className="text-gray-600">For quick testing without exposing API key. Agent ID embedded in token.</p>
                  <div className="flex space-x-1">
                    <input
                      type="text"
                      placeholder="Click Generate & Copy Test Token"
                      readOnly
                      className="input flex-1 font-mono text-xs bg-gray-100"
                      id="testTokenDisplay"
                    />
                    <button
                      onClick={async () => {
                        try {
                          const data = await api.getWebSocketTestToken(agentId);
                          const display = document.getElementById('testTokenDisplay') as HTMLInputElement;
                          display.value = data.test_token;
                          copyToClipboard(data.test_token);
                          toast.success('Test token copied to clipboard');
                        } catch (e) {
                          toast.error('Failed to generate test token');
                        }
                      }}
                      className="btn-secondary text-sm"
                    >
                      <KeyIcon className="w-4 h-4 mr-1" />
                      Generate & Copy Test Token
                    </button>
                  </div>
                  <p className="text-green-600 text-xs">✅ <code>agent_id</code> embedded — no config needed for agent resolution</p>
                </div>
              </div>
            </div>

            {/* Complete Config Schema */}
            <details className="group border border-gray-200 rounded-lg">
              <summary className="p-4 cursor-pointer font-semibold text-gray-900 flex items-center justify-between">
                <span>📋 Complete Configuration Schema (All Fields Passed at Connection)</span>
                <span className="text-gray-400">Click to expand</span>
              </summary>
              <div className="p-4 border-t border-gray-200 bg-gray-50">
                <p className="text-sm text-gray-600 mb-3">All agent configuration passed in first <code>config</code> message — NO portal setup needed.</p>
                <pre className="bg-gray-900 text-green-300 p-3 rounded text-xs overflow-x-auto max-h-96 overflow-y-auto">
{`{
  "type": "config",
  "data": {
    // Required
    "direction": "outbound|inbound",
    "system_prompt": "You are a helpful AI assistant...",

    // Optional - for your tracking
    "agent_id": "your-internal-tracking-id",
    "metadata": {"campaign": "summer_sale", "source": "web"},

    // Voice Stack
    "voice_stack": "stack_a|stack_b",

    // Outbound Prompts
    "opening_line": "Hi, this is Sarah from Acme Corp...",
    "objective_prompt": "Schedule a 15-minute demo call.",
    "objection_handling_prompt": "If not interested: 'I understand...'",
    "voicemail_prompt": "Hi, this is Sarah... Please call back.",
    "closing_prompt": "Great! I'll send a calendar invite.",
    "escalation_rule": "If asked for manager: 'I'll have my manager reach out.'",

    // Inbound Prompts
    "greeting_prompt": "Thanks for calling Acme Corp! How can I help?",
    "qualification_prompt": "What brings you to call today?",
    "knowledge_prompt": "Our product does X, Y, Z...",
    "fallback_prompt": "I don't have that info, let me transfer you.",
    "handoff_prompt": "Connecting you to a human agent...",

    // Shared Settings
    "interruption_sensitivity": "low|medium|high",
    "max_call_duration_s": 300,
    "silence_timeout_s": 10,
    "language": "en-US",
    "stt_engine": "faster-whisper|riva-asr",
    "tts_engine": "kokoro|piper|chatterbox",
    "tts_voice": "af_heart|...",
    "llm_provider": "nvidia_integrate",
    "llm_model": "stepfun-ai/step-3.7-flash",

    // Stack B (NVIDIA NIM) - Optional
    "chatterbox_voice": "Chatterbox-Multilingual.en-US.Female",
    "chatterbox_emotion_exaggeration": 0.5,
    "riva_asr_language": "en-US",
    "riva_vad_threshold": 0.5
  }
}`}
                </pre>
              </div>
            </details>

            {/* Message Flow */}
            <details className="group border border-gray-200 rounded-lg">
              <summary className="p-4 cursor-pointer font-semibold text-gray-900 flex items-center justify-between">
                <span>🔄 Message Flow Protocol</span>
                <span className="text-gray-400">Click to expand</span>
              </summary>
              <div className="p-4 border-t border-gray-200 bg-gray-50 space-y-3">
                <div className="space-y-2 text-sm">
                  <div className="font-mono text-green-600 bg-gray-100 p-2 rounded">1. CONNECT</div>
                  <pre className="bg-gray-900 text-green-300 p-2 rounded text-xs">{`Server → Client:
{
  "type": "ready",
  "data": {
    "session_id": "uuid",
    "protocol_version": "1.0",
    "auth_method": "api_key|test_token",
    "audio_format": {
      "sample_rate": 16000,
      "channels": 1,
      "encoding": "int16",
      "frame_ms": 20
    },
    "supported_stacks": ["stack_a", "stack_b"]
  }
}`}</pre>
                </div>

                <div className="space-y-2 text-sm">
                  <div className="font-mono text-blue-600 bg-gray-100 p-2 rounded">2. CONFIG (Required - First Message)</div>
                  <pre className="bg-gray-900 text-blue-300 p-2 rounded text-xs">{`Client → Server:
{
  "type": "config",
  "data": { /* FULL AGENT CONFIG FROM ABOVE */ }
}`}</pre>
                </div>

                <div className="space-y-2 text-sm">
                  <div className="font-mono text-purple-600 bg-gray-100 p-2 rounded">3. STARTED</div>
                  <pre className="bg-gray-900 text-purple-300 p-2 rounded text-xs">{`Server → Client:
{
  "type": "started",
  "data": {
    "session_id": "uuid",
    "capabilities": ["barge_in", "streaming_stt", "streaming_tts", "interruption_detection"],
    "stack": "faster-whisper",
    "started_at": "2026-08-17T10:30:00Z"
  }
}`}</pre>
                </div>

                <div className="space-y-2 text-sm">
                  <div className="font-mono text-orange-600 bg-gray-100 p-2 rounded">4. EXCHANGE (Continuous)</div>
                  <pre className="bg-gray-900 text-orange-300 p-2 rounded text-xs">{`// Binary Audio Frames (int16, 16kHz, mono, 20ms = 640 bytes)
ws.send(audioBuffer)

// JSON Control Messages:
{"type": "transcript", "data": {"turn_id": 1, "role": "assistant", "text": "Hello!", "timestamp": "...", "interrupted": false}}
{"type": "state", "data": "listening|processing|speaking"}
{"type": "dtmf_received", "data": {"digit": "1"}}
{"type": "error", "data": {"message": "...", "code": "..."}}`}</pre>
                </div>

                <div className="space-y-2 text-sm">
                  <div className="font-mono text-red-600 bg-gray-100 p-2 rounded">5. END</div>
                  <pre className="bg-gray-900 text-red-300 p-2 rounded text-xs">{`Client → Server:     Server → Client:
{"type": "end"}       {"type": "ended", "data": {
                       "session_id": "...",
                       "transcript": [...],
                       "duration_seconds": 45.2,
                       "ended_at": "..."
                     }}`}</pre>
                </div>
              </div>
            </details>

            {/* Connection Examples */}
            <div className="pt-4 border-t border-gray-200">
              <h3 className="font-semibold text-gray-900 mb-3">Connection Examples</h3>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <p className="text-xs text-gray-500 mb-1">JavaScript (Browser/Node) - API Key Auth</p>
                  <pre className="bg-gray-900 text-green-300 p-3 rounded text-xs overflow-x-auto">
{`const ws = new WebSocket(
  'wss://ominivoice.local/ws?api_key=YOUR_API_KEY'
);

ws.onopen = () => {
  console.log('Connected');
  ws.send(JSON.stringify({
    type: 'config',
    data: {
      agent_id: '${agentId}',
      direction: 'outbound',
      system_prompt: 'You are a helpful AI assistant...',
      voice_stack: 'stack_a',
      opening_line: 'Hi, this is a test call.',
      objective_prompt: 'Verify connection works.',
      interruption_sensitivity: 'medium',
      max_call_duration_s: 60,
      silence_timeout_s: 5,
      language: 'en-US',
      stt_engine: 'faster-whisper',
      tts_engine: 'kokoro',
      tts_voice: 'af_heart',
      llm_provider: 'nvidia_integrate',
      llm_model: 'stepfun-ai/step-3.7-flash'
    }
  }));
};

ws.onmessage = (event) => {
  if (event.data instanceof ArrayBuffer) {
    // Audio from TTS - play it
    playAudio(event.data);
  } else {
    const msg = JSON.parse(event.data);
    if (msg.type === 'transcript') console.log(msg.data.role + ': ' + msg.data.text);
    if (msg.type === 'state') console.log('State: ' + msg.data);
    if (msg.type === 'ended') console.log('Call ended: ' + msg.data.duration_seconds + 's');
  }
};

// Send audio (int16, 16kHz, mono, 20ms frames)
ws.send(audioBuffer);`}
                  </pre>
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1">Python (Asterisk/FreeSWITCH/Twilio) - Test Token</p>
                  <pre className="bg-gray-900 text-green-300 p-3 rounded text-xs overflow-x-auto">
{`import asyncio
import websockets
import json
import numpy as np

async def connect_agent():
    # Test token - agent_id embedded, no config needed for agent resolution
    token = "YOUR_TEST_TOKEN"
    uri = f"wss://ominivoice.local/ws?token={token}"

    async with websockets.connect(uri, ping_interval=20) as ws:
        # 1. Wait for READY
        ready = json.loads(await ws.recv())
        print(f"Ready: {ready['data']['session_id']}")

        # 2. Send FULL config (still required for voice setup)
        await ws.send(json.dumps({
            "type": "config",
            "data": {
                "direction": "outbound",
                "system_prompt": "You are a helpful AI...",
                "voice_stack": "stack_a",
                "opening_line": "Hello from external system!",
                "objective_prompt": "Test the integration.",
                "interruption_sensitivity": "medium",
                "max_call_duration_s": 60,
                "silence_timeout_s": 5,
                "language": "en-US",
                "stt_engine": "faster-whisper",
                "tts_engine": "kokoro",
                "tts_voice": "af_heart",
                "llm_provider": "nvidia_integrate",
                "llm_model": "stepfun-ai/step-3.7-flash"
            }
        }))

        # 3. Wait for STARTED
        started = json.loads(await ws.recv())
        print(f"Started: {started['data']['capabilities']}")

        # 4. Exchange audio + handle messages
        async def send_audio():
            while True:
                chunk = get_audio_from_sip_rtp()  # Your SIP media handler
                await ws.send(chunk.tobytes())
                await asyncio.sleep(0.02)

        async def recv_messages():
            async for msg in ws:
                if isinstance(msg, bytes):
                    play_audio_to_caller(msg)  # Your SIP media handler
                else:
                    data = json.loads(msg)
                    if data['type'] == 'transcript':
                        print(f"{data['data']['role']}: {data['data']['text']}")
                    elif data['type'] == 'ended':
                        break

        await asyncio.gather(send_audio(), recv_messages())

        # 5. End
        await ws.send(json.dumps({"type": "end"}))

# For API key auth (production):
# uri = f"wss://ominivoice.local/ws?api_key=ov_live_..."
# config must include "agent_id": "your-tracking-id"`}
                  </pre>
                </div>
              </div>
            </div>

            {/* Audio Format Spec */}
            <div className="pt-4 border-t border-gray-200 bg-gray-50 rounded-lg p-4">
              <h4 className="font-semibold text-gray-900 mb-2">🎵 Audio Format Specification</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div className="font-mono bg-gray-100 p-2 rounded">Sample Rate: 16,000 Hz</div>
                <div className="font-mono bg-gray-100 p-2 rounded">Channels: 1 (Mono)</div>
                <div className="font-mono bg-gray-100 p-2 rounded">Encoding: int16 (16-bit PCM)</div>
                <div className="font-mono bg-gray-100 p-2 rounded">Frame: 20ms (320 samples = 640 bytes)</div>
              </div>
              <p className="text-xs text-gray-500 mt-2">Send raw int16 binary frames. Server returns same format for TTS audio.</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

