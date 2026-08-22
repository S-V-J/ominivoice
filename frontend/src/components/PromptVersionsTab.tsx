import { useEffect, useState } from 'react';
import { api } from '../services/api';
import toast from 'react-hot-toast';
import type { AgentPromptVersion } from '../types';

interface PromptVersionsTabProps {
  agentId: string;
}

export default function PromptVersionsTab({ agentId }: PromptVersionsTabProps) {
  const [versions, setVersions] = useState<AgentPromptVersion[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedField, setSelectedField] = useState<string>('');

  useEffect(() => {
    loadVersions();
  }, [agentId, selectedField]);

  const loadVersions = async () => {
    setIsLoading(true);
    try {
      const data = await api.getPromptVersions(agentId, selectedField || undefined);
      setVersions(data);
    } catch (err) {
      toast.error('Failed to load version history');
    } finally {
      setIsLoading(false);
    }
  };

  const fields = [
    'system_prompt', 'opening_line', 'objective_prompt', 'objection_handling_prompt',
    'voicemail_prompt', 'closing_prompt', 'escalation_rule',
    'greeting_prompt', 'qualification_prompt', 'knowledge_prompt',
    'fallback_prompt', 'handoff_prompt',
  ];

  return (
    <div className="space-y-4">
      <div className="card">
        <div className="card-body">
          <label className="label mb-2">Filter by field</label>
          <select
            value={selectedField}
            onChange={(e) => setSelectedField(e.target.value)}
            className="input w-auto"
          >
            <option value="">All fields</option>
            {fields.map((f) => (
              <option key={f} value={f}>{f.replace(/_/g, ' ')}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="card">
        {isLoading ? (
          <div className="card-body flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-4 border-primary-600 border-t-transparent"></div>
          </div>
        ) : versions.length === 0 ? (
          <div className="card-body text-center py-8 text-gray-500">
            No prompt versions yet. Changes to prompt fields will be tracked here.
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {versions.map((v) => (
              <div key={v.id} className="card-body py-4">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <span className="font-medium text-gray-900">{v.field_name.replace(/_/g, ' ')}</span>
                    <span className="ml-3 text-sm text-gray-500">
                      {new Date(v.edited_at).toLocaleString()}
                    </span>
                  </div>
                  <span className="badge badge-gray">v{versions.indexOf(v) + 1}</span>
                </div>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-gray-500 mb-1">Previous</p>
                    <pre className="bg-gray-50 p-3 rounded text-gray-700 whitespace-pre-wrap max-h-32 overflow-auto">
                      {v.old_value || '(empty)'}
                    </pre>
                  </div>
                  <div>
                    <p className="text-gray-500 mb-1">New</p>
                    <pre className="bg-green-50 p-3 rounded text-gray-700 whitespace-pre-wrap max-h-32 overflow-auto">
                      {v.new_value || '(empty)'}
                    </pre>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}