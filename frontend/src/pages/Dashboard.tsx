import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAgentStore } from '../store/agentStore';
import { api } from '../services/api';
import toast from 'react-hot-toast';
import type { AgentDirection } from '../types';
import {
  PlusIcon,
  MicrophoneIcon,
  PhoneArrowUpRightIcon,
  PhoneArrowDownLeftIcon,
  DocumentTextIcon,
} from '@heroicons/react/24/outline';

export default function Dashboard() {
  const { agents, setAgents, setLoading, addAgent } = useAgentStore();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newAgentName, setNewAgentName] = useState('');
  const [newAgentDirection, setNewAgentDirection] = useState<AgentDirection>('outbound');
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    loadAgents();
  }, []);

  const loadAgents = async () => {
    setLoading(true);
    try {
      const data = await api.listAgents();
      setAgents(data);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to load agents');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateAgent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAgentName.trim()) return;

    setIsCreating(true);
    try {
      const agent = await api.createAgent({
        name: newAgentName.trim(),
        direction: newAgentDirection,
      });
      addAgent(agent);
      toast.success('Agent created!');
      setShowCreateModal(false);
      setNewAgentName('');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to create agent');
    } finally {
      setIsCreating(false);
    }
  };

  const getDirectionIcon = (direction: AgentDirection) => {
    return direction === 'outbound' ? (
      <PhoneArrowUpRightIcon className="w-5 h-5 text-blue-600" />
    ) : (
      <PhoneArrowDownLeftIcon className="w-5 h-5 text-green-600" />
    );
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-600">Manage your voice agents</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="btn-primary"
        >
          <PlusIcon className="w-5 h-5 mr-2" />
          New Agent
        </button>
      </div>

      {agents.length === 0 ? (
        <div className="card p-12 text-center">
          <MicrophoneIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No agents yet</h3>
          <p className="text-gray-500 mb-6">Create your first voice agent to get started</p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="btn-primary"
          >
            <PlusIcon className="w-5 h-5 mr-2" />
            Create Agent
          </button>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {agents.map((agent) => (
            <Link
              key={agent.id}
              to={`/agents/${agent.id}`}
              className="card hover:shadow-md transition-shadow"
            >
              <div className="card-body">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center">
                      <MicrophoneIcon className="w-5 h-5 text-primary-600" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-900">{agent.name}</h3>
                      <p className="text-sm text-gray-500 capitalize">{agent.direction}</p>
                    </div>
                  </div>
                  <span className={`badge ${getStatusBadge(agent.status)}`}>
                    {agent.status}
                  </span>
                </div>

                <div className="flex items-center space-x-4 text-sm text-gray-500 mb-4">
                  <span className="flex items-center">
                    {getDirectionIcon(agent.direction)}
                    <span className="ml-1 capitalize">{agent.direction}</span>
                  </span>
                  <span className="flex items-center">
                    <DocumentTextIcon className="w-4 h-4 mr-1" />
                    {agent.completeness_percentage}% complete
                  </span>
                </div>

                <div className="flex items-center justify-between pt-4 border-t border-gray-100">
                  <span className="text-xs text-gray-400">
                    Updated {new Date(agent.updated_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Create Agent Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => setShowCreateModal(false)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-md mx-4" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-xl font-bold text-gray-900 mb-4">Create New Agent</h2>
            <form onSubmit={handleCreateAgent}>
              <div className="mb-4">
                <label className="label">Agent Name</label>
                <input
                  type="text"
                  value={newAgentName}
                  onChange={(e) => setNewAgentName(e.target.value)}
                  className="input"
                  placeholder="e.g., Sales Outreach Agent"
                  autoFocus
                  required
                />
              </div>
              <div className="mb-6">
                <label className="label">Direction</label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setNewAgentDirection('outbound')}
                    className={`p-3 rounded-lg border-2 text-center transition-colors ${
                      newAgentDirection === 'outbound'
                        ? 'border-primary-500 bg-primary-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <PhoneArrowUpRightIcon className="w-6 h-6 mx-auto mb-1 text-gray-600" />
                    <p className="text-sm font-medium text-gray-900">Outbound</p>
                    <p className="text-xs text-gray-500">Agent initiates calls</p>
                  </button>
                  <button
                    type="button"
                    onClick={() => setNewAgentDirection('inbound')}
                    className={`p-3 rounded-lg border-2 text-center transition-colors ${
                      newAgentDirection === 'inbound'
                        ? 'border-green-500 bg-green-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <PhoneArrowDownLeftIcon className="w-6 h-6 mx-auto mb-1 text-gray-600" />
                    <p className="text-sm font-medium text-gray-900">Inbound</p>
                    <p className="text-xs text-gray-500">Agent receives calls</p>
                  </button>
                </div>
              </div>
              <div className="flex space-x-3">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="btn-secondary flex-1"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreating || !newAgentName.trim()}
                  className="btn-primary flex-1"
                >
                  {isCreating ? 'Creating...' : 'Create Agent'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}