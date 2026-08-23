import { useState, useEffect } from 'react';
import { useAuthStore } from '../store/authStore';
import { useDemoCall } from '../hooks/useDemoCall';
import { api } from '../services/api';
import toast from 'react-hot-toast';
import type { Agent, AgentDirection, PlanTier, UpgradePlanTier, UsageStats } from '../types';
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
  CreditCardIcon,
  CalendarIcon,
  CurrencyDollarIcon,
  DocumentTextIcon,
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

const PLAN_DETAILS: Record<string, { name: string; price: string; features: string[] }> = {
  free: {
    name: 'Free',
    price: '$0/month',
    features: [
      'Up to 3 voice agents',
      '100 test call minutes/month',
      'Basic prompt templates',
      'Community support',
      'Simulated calls only',
    ],
  },
  starter: {
    name: 'Starter',
    price: '$29/month',
    features: [
      'Up to 10 voice agents',
      '1,000 test call minutes/month',
      'AI prompt rewriting',
      'Email support',
      'Webhook integration',
      'Prompt version history',
    ],
  },
  pro: {
    name: 'Pro',
    price: '$99/month',
    features: [
      'Unlimited voice agents',
      '10,000 test call minutes/month',
      'Cold-call queue automation',
      'Priority email support',
      'Advanced analytics',
      'Custom webhook URLs',
      'API rate limit increases',
    ],
  },
  enterprise: {
    name: 'Enterprise',
    price: 'Custom',
    features: [
      'Everything in Pro',
      'Unlimited minutes',
      'Dedicated support',
      'SLA guarantee',
      'Custom integrations',
      'On-premise deployment option',
      'SSO/SAML authentication',
      'Audit logs',
    ],
  },
};

type PlanTier = 'free' | 'starter' | 'pro' | 'enterprise';
type UpgradePlanTier = 'starter' | 'pro' | 'enterprise';
type AgentDirection = 'inbound' | 'outbound';
type AgentStatus = 'draft' | 'active' | 'paused' | 'archived';

interface UsageStats {
  plan: string;
  period_start: string;
  period_end: string;
  agents_used: number;
  agents_limit: number | null;
  minutes_used: number;
  minutes_limit: number | null;
  queue_rows_used: number;
  queue_rows_limit: number | null;
}

interface Agent {
  id: string;
  name: string;
  direction: AgentDirection;
  status: AgentStatus;
  owner_id: string;
  voice_stack?: string;
  system_prompt?: string;
  opening_line?: string;
  objective_prompt?: string;
  objection_handling_prompt?: string;
  voicemail_prompt?: string;
  closing_prompt?: string;
  escalation_rule?: string;
  greeting_prompt?: string;
  qualification_prompt?: string;
  knowledge_prompt?: string;
  fallback_prompt?: string;
  handoff_prompt?: string;
  interruption_sensitivity?: string;
  max_call_duration_s?: number;
  silence_timeout_s?: number;
  language?: string;
  stt_engine?: string;
  tts_engine?: string;
  tts_voice?: string;
  chatterbox_voice?: string;
  chatterbox_emotion_exaggeration?: number;
  riva_asr_language?: string;
  riva_vad_threshold?: number;
  llm_provider?: string;
  llm_model?: string;
  created_at: string;
  updated_at: string;
}

export default function Account() {
  const { user } = useAuthStore();
  const [usage, setUsage] = useState<UsageStats | null>(null);

  const currentPlan = (user?.plan as string) || 'free';
  const planDetails = PLAN_DETAILS[currentPlan];

  useEffect(() => {
    loadUsage();
  }, []);

  const loadUsage = async () => {
    try {
      const data = await api.getUsageStats();
      setUsage(data);
    } catch (err) {
      console.error('Failed to load usage stats:', err);
    }
  };

  const handleManageBilling = async () => {
    try {
      const data = await api.createPortalSession();
      window.location.href = data.url;
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to open billing portal');
    }
  };

  const [showCheckout, setShowCheckout] = useState<string | null>(null);

  const handleUpgrade = (plan: string) => {
    if (plan === 'enterprise') {
      toast('Contact sales for Enterprise pricing', { icon: 'ℹ️' });
      return;
    }
    setShowCheckout(plan);
  };

  const handleCheckoutSuccess = () => {
    setShowCheckout(null);
    toast.success('Subscription activated!');
    loadUsage();
  };

  const handleCheckoutCancel = () => {
    setShowCheckout(null);
  };

  const getProgress = (used: number, limit: number | null) => {
    if (!limit) return 100;
    return Math.min(100, Math.round((used / limit) * 100));
  };

  const getProgressColor = (percentage: number) => {
    if (percentage >= 90) return 'bg-red-500';
    if (percentage >= 70) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  const handleManageBilling = async () => {
    try {
      const data = await api.createPortalSession();
      window.location.href = data.url;
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to open billing portal');
    }
  };

  const handleUpgrade = (plan: string) => {
    if (plan === 'enterprise') {
      toast('Contact sales for Enterprise pricing', { icon: 'ℹ️' });
      return;
    }
    setShowCheckout(plan);
  };

  const handleCheckoutSuccess = () => {
    setShowCheckout(null);
    toast.success('Subscription activated!');
    loadUsage();
  };

  const handleCheckoutCancel = () => {
    setShowCheckout(null);
  };

  const getProgress = (used: number, limit: number | null) => {
    if (!limit) return 100;
    return Math.min(100, Math.round((used / limit) * 100));
  };

  const getProgressColor = (percentage: number) => {
    if (percentage >= 90) return 'bg-red-500';
    if (percentage >= 70) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Account & Billing</h1>
        <p className="mt-2 text-gray-600">Manage your subscription, usage, and billing details</p>
      </div>

      {/* Current Plan Card */}
      <div className="card">
        <div className="card-header">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Current Plan</h2>
              <p className="text-sm text-gray-500 mt-1">{planDetails.name} · {planDetails.price}</p>
            </div>
            {currentPlan !== 'enterprise' && (
              <button
                onClick={() => handleUpgrade(currentPlan === 'free' ? 'starter' : 'pro')}
                className="btn-primary"
              >
                {currentPlan === 'free' ? 'Upgrade' : 'Change Plan'}
              </button>
            )}
          </div>
        </div>
        <div className="card-body">
          <div className="grid gap-6 md:grid-cols-3">
            {/* Agents Usage */}
            <div className="bg-gray-50 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-900">Voice Agents</span>
                <span className="text-sm text-gray-500">
                  {usage?.agents_used ?? 0} / {usage?.agents_limit ?? (currentPlan === 'free' ? 3 : '∞')}
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`${getProgressColor(getProgress(usage?.agents_used ?? 0, usage?.agents_limit ?? (currentPlan === 'free' ? 3 : 100)))} h-2 rounded-full transition-all`}
                  style={{ width: `${getProgress(usage?.agents_used ?? 0, usage?.agents_limit ?? (currentPlan === 'free' ? 3 : 100))}%` }}
                ></div>
              </div>
            </div>

            {/* Minutes Usage */}
            <div className="bg-gray-50 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-900">Test Call Minutes</span>
                <span className="text-sm text-gray-500">
                  {usage?.minutes_used ?? 0} / {usage?.minutes_limit ?? (currentPlan === 'free' ? 100 : '∞')}
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`${getProgressColor(getProgress(usage?.minutes_used ?? 0, usage?.minutes_limit ?? (currentPlan === 'free' ? 100 : 10000)))} h-2 rounded-full transition-all`}
                  style={{ width: `${getProgress(usage?.minutes_used ?? 0, usage?.minutes_limit ?? (currentPlan === 'free' ? 100 : 10000))}%` }}
                ></div>
              </div>
            </div>

            {/* Queue Rows Usage */}
            <div className="bg-gray-50 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-900">Queue Rows</span>
                <span className="text-sm text-gray-500">
                  {usage?.queue_rows_used ?? 0} / {usage?.queue_rows_limit ?? (currentPlan === 'free' ? 0 : '∞')}
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`${getProgressColor(getProgress(usage?.queue_rows_used ?? 0, usage?.queue_rows_limit ?? (currentPlan === 'free' ? 0 : 10000)))} h-2 rounded-full transition-all`}
                  style={{ width: `${getProgress(usage?.queue_rows_used ?? 0, usage?.queue_rows_limit ?? (currentPlan === 'free' ? 0 : 10000))}%` }}
                ></div>
              </div>
            </div>
          </div>

          {/* Period info */}
          {usage && (
            <div className="mt-6 pt-6 border-t border-gray-200 flex items-center justify-between text-sm text-gray-500">
              <span>
                <CalendarIcon className="w-4 h-4 inline mr-1" />
                Billing Period: {new Date(usage.period_start).toLocaleDateString()} — {new Date(usage.period_end).toLocaleDateString()}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Plan Comparison */}
      <div className="card">
        <div className="card-header">
          <h2 className="text-lg font-semibold text-gray-900">Available Plans</h2>
          <p className="text-sm text-gray-500 mt-1">Compare features and choose the right plan for you</p>
        </div>
        <div className="card-body">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Feature</th>
                  {(['free', 'starter', 'pro', 'enterprise'] as const).map((plan) => (
                    <th key={plan} className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      <div className={`font-semibold text-gray-900 ${currentPlan === plan ? 'text-primary-600' : ''}`}>{PLAN_DETAILS[plan].name}</div>
                      <div className="text-sm text-gray-500">{PLAN_DETAILS[plan].price}</div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {PLAN_DETAILS.free.features.map((feature, idx) => (
                  <tr key={idx}>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">{feature}</td>
                    {(['free', 'starter', 'pro', 'enterprise'] as const).map((plan) => (
                      <td key={plan} className="px-4 py-3 text-center">
                        {PLAN_DETAILS[plan].features.includes(feature) ? (
                          <svg className="w-5 h-5 text-green-500 mx-auto" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/></svg>
                        ) : (
                          <svg className="w-5 h-5 text-gray-300 mx-auto" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd"/></svg>
                        )}
                      )}
                    </td>
                  ))}
                ))}
              </tbody>
            </table>
          </div>

          {/* Upgrade buttons */}
          {showCheckout ? (
            <StripeCheckout
              plan={showCheckout}
              onSuccess={handleCheckoutSuccess}
              onCancel={handleCheckoutCancel}
            />
          ) : (
            <div className="mt-6 grid gap-4 md:grid-cols-4">
              {(['starter', 'pro', 'enterprise'] as const).map((plan) => {
                // Use explicit type narrowing with a const array that TypeScript understands
                const upgradePlans = ['starter', 'pro', 'enterprise'] as const;
                const isUpgrade = upgradePlans.includes(currentPlan);
                const isCurrentPlan = isUpgrade && currentPlan === plan;
                return (
                  <button
                    key={plan}
                    onClick={() => handleUpgrade(plan)}
                    disabled={isCurrentPlan || plan === 'enterprise'}
                    className={`py-3 px-4 rounded-lg font-medium text-center transition-colors ${
                      isCurrentPlan
                        ? 'bg-gray-100 text-gray-500 cursor-not-allowed'
                        : plan === 'enterprise'
                        ? 'bg-gray-100 text-gray-500 cursor-not_allowed'
                        : plan === 'pro'
                        ? 'bg-primary-600 text-white hover:bg-primary-700'
                        : 'bg-gray-900 text-white hover:bg-gray-800'
                    }`}
                  >
                    {isCurrentPlan ? 'Current Plan' : plan === 'enterprise' ? 'Contact Sales' : `Upgrade to ${PLAN_DETAILS[plan].name}`}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Billing Actions */}
      <div className="card">
        <div className="card-header">
          <h2 className="text-lg font-semibold text-gray-900">Billing Management</h2>
        </div>
        <div className="card-body space-y-4">
          <button
            onClick={handleManageBilling}
            className="btn-primary flex items-center justify-center"
            disabled={currentPlan === 'free'}
          >
            <CreditCardIcon className="w-5 h-5 mr-2" />
            {currentPlan === 'free' ? 'Upgrade to access billing portal' : 'Manage Billing (Stripe Portal)'}
          </button>
          {currentPlan === 'free' && (
            <p className="text-sm text-gray-500 text-center">
              Upgrade to a paid plan to access the Stripe customer portal for payment methods, invoices, and subscription management.
            </p>
          )}
        </div>
      </div>

      {/* Invoice History (Placeholder) */}
      <div className="card">
        <div className="card-header flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Invoice History</h2>
          <DocumentTextIcon className="w-5 h-5 text-gray-400" />
        </div>
        <div className="card-body">
          {currentPlan === 'free' ? (
            <div className="text-center py-8">
              <CurrencyDollarIcon className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500">No invoices yet. Invoices will appear here after upgrading to a paid plan.</p>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-gray-500">Invoice history will be loaded from Stripe. This is a placeholder for Phase 8 implementation.</p>
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600">INV-2026-001</span>
                  <span className="text-gray-900 font-medium">$29.00</span>
                  <span className="text-green-600">Paid</span>
                  <span className="text-gray-500">Aug 1, 2026</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StripeCheckout({ plan, onSuccess, onCancel }: { plan: string; onSuccess: () => void; onCancel: () => void }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCheckout = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.createCheckoutSession(plan);
      if (response.url) {
        window.location.href = response.url;
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create checkout session');
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-xl p-6 w-full max-w-md mx-4">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary-600 border-t-transparent mx-auto mb-4"></div>
          <p className="text-center text-gray-600">Redirecting to Stripe Checkout...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto">
      <div className="card">
        <div className="card-header">
          <h2 className="text-lg font-semibold text-gray-900">Subscribe to {PLAN_DETAILS[plan].name}</h2>
          <p className="text-sm text-gray-500 mt-1">{PLAN_DETAILS[plan].price}</p>
        </div>
        <div className="card-body">
          <ul className="space-y-2 text-sm text-gray-600">
            {PLAN_DETAILS[plan as keyof typeof PLAN_DETAILS].features.map((feature) => (
              <li key={feature} className="flex items-center">
                <svg className="w-5 h-5 text-green-500 mr-2" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/></svg>
                <span>{feature}</span>
              </li>
            ))}
          </ul>
          {error && (
            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {error}
            </div>
          )}
          <div className="mt-6 flex space-x-3">
            <button
              onClick={handleCheckout}
              disabled={loading}
              className="btn-primary flex-1"
            >
              {loading ? 'Processing...' : `Subscribe to ${PLAN_DETAILS[plan].name}`}
            </button>
            <button
              onClick={onCancel}
              className="btn-secondary"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    );
  }

  const planDetails = PLAN_DETAILS[plan as keyof typeof PLAN_DETAILS] || PLAN_DETAILS.starter;
  return <StripeCheckout plan={plan} onSuccess={onSuccess} onCancel={onCancel} />;
}

export default Account;
