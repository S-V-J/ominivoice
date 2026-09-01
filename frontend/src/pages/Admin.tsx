import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import toast from 'react-hot-toast';
import {
  UsersIcon,
  MicrophoneIcon,
  PhoneIcon,
  CurrencyDollarIcon,
  ChartBarIcon,
  ExclamationTriangleIcon,
  MagnifyingGlassIcon,
  ArrowLeftIcon,
  PauseIcon,
  PlayIcon,
  TrashIcon,
  EyeIcon,
  DocumentTextIcon,
  Cog6ToothIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline';

interface AdminStats {
  total_users: number;
  active_users: number;
  total_agents: number;
  total_calls_30d: number;
  calls_per_minute: number;
  queue_depth: number;
  monthly_revenue: number;
}

interface AdminUser {
  id: string;
  email: string;
  plan: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  agent_count: number;
  subscription_status: string | null;
  subscription_plan: string | null;
}

interface AdminAgent {
  id: string;
  name: string;
  direction: 'inbound' | 'outbound';
  status: string;
  owner_email: string;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

interface AuditLog {
  id: string;
  user_id: string | null;
  account_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  old_values: any;
  new_values: any;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

type Tab = 'overview' | 'users' | 'agents' | 'audit' | 'settings';

export default function Admin() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [agents, setAgents] = useState<AdminAgent[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Pagination
  const [userPage, setUserPage] = useState(1);
  const [agentPage, setAgentPage] = useState(1);
  const [auditPage, setAuditPage] = useState(1);
  const pageSize = 20;

  // Filters
  const [userSearch, setUserSearch] = useState('');
  const [agentStatusFilter, setAgentStatusFilter] = useState('');
  const [auditActionFilter, setAuditActionFilter] = useState('');

  useEffect(() => {
    loadStats();
    loadUsers();
    loadAgents();
    loadAuditLogs();
  }, []);

  const loadStats = async () => {
    try {
      const data = await api.get('/admin/stats');
      setStats(data);
    } catch (err: any) {
      if (err.response?.status === 403) {
        navigate('/dashboard');
        toast.error('Admin access required');
      } else {
        setError(err.response?.data?.detail || 'Failed to load stats');
      }
    }
  };

  const loadUsers = async () => {
    setLoading(true);
    try {
      const data = await api.get('/admin/users', {
        params: {
          search: userSearch || undefined,
          page: userPage,
          page_size: pageSize,
        },
      });
      setUsers(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  const loadAgents = async () => {
    setLoading(true);
    try {
      const data = await api.get('/admin/agents', {
        params: {
          status_filter: agentStatusFilter || undefined,
          page: agentPage,
          page_size: pageSize,
        },
      });
      setAgents(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load agents');
    } finally {
      setLoading(false);
    }
  };

  const loadAuditLogs = async () => {
    setLoading(true);
    try {
      const data = await api.get('/admin/audit-logs', {
        params: {
          action: auditActionFilter || undefined,
          page: auditPage,
          page_size: pageSize,
        },
      });
      setAuditLogs(data.logs);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load audit logs');
    } finally {
      setLoading(false);
    }
  };

  const handleSuspendUser = async (userId: string, email: string, suspend: boolean) => {
    if (!confirm(`${suspend ? 'Suspend' : 'Unsuspend'} user ${email}?`)) return;
    try {
      await api.post(`/admin/users/${userId}/${suspend ? 'suspend' : 'unsuspend'}`);
      toast.success(`User ${suspend ? 'suspended' : 'unsuspended'}`);
      loadUsers();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update user');
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount);
  };

  const getPlanBadge = (plan: string) => {
    const badges: Record<string, string> = {
      free: 'badge-gray',
      starter: 'badge-blue',
      pro: 'badge-purple',
      enterprise: 'badge-gold',
    };
    return badges[plan] || 'badge-gray';
  };

  const getStatusBadge = (status: string) => {
    const badges: Record<string, string> = {
      active: 'badge-success',
      inactive: 'badge-gray',
      draft: 'badge-gray',
      paused: 'badge-warning',
      archived: 'badge-info',
    };
    return badges[status] || 'badge-gray';
  };

  if (!stats && activeTab === 'overview') {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary-600 border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <button onClick={() => navigate('/dashboard')} className="text-gray-500 hover:text-gray-700">
            <ArrowLeftIcon className="w-6 h-6" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Admin Dashboard</h1>
            <p className="text-sm text-gray-500">Platform administration and monitoring</p>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <span className="badge badge-red flex items-center">
            <ShieldCheckIcon className="w-4 h-4 mr-1" />
            Admin Mode
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8 overflow-x-auto" aria-label="Admin tabs">
          {[
            { id: 'overview', label: 'Overview', icon: ChartBarIcon },
            { id: 'users', label: 'Users', icon: UsersIcon },
            { id: 'agents', label: 'Agents', icon: MicrophoneIcon },
            { id: 'audit', label: 'Audit Logs', icon: DocumentTextIcon },
            { id: 'settings', label: 'Settings', icon: Cog6ToothIcon },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as Tab)}
              className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm whitespace-nowrap transition-colors ${
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
      {activeTab === 'overview' && (
        <OverviewTab stats={stats} />
      )}

      {activeTab === 'users' && (
        <UsersTab
          users={users}
          loading={loading}
          page={userPage}
          setPage={setUserPage}
          search={userSearch}
          setSearch={setUserSearch}
          onSuspend={handleSuspendUser}
        />
      )}

      {activeTab === 'agents' && (
        <AgentsTab
          agents={agents}
          loading={loading}
          page={agentPage}
          setPage={setAgentPage}
          statusFilter={agentStatusFilter}
          setStatusFilter={setAgentStatusFilter}
        />
      )}

      {activeTab === 'audit' && (
        <AuditTab
          logs={auditLogs}
          loading={loading}
          page={auditPage}
          setPage={setAuditPage}
          actionFilter={auditActionFilter}
          setActionFilter={setAuditActionFilter}
        />
      )}

      {activeTab === 'settings' && (
        <SettingsTab />
      )}
    </div>
  );
}

function OverviewTab({ stats }: { stats: AdminStats | null }) {
  if (!stats) return null;

  return (
    <div className="space-y-6">
      {/* Key Metrics */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Total Users"
          value={stats.total_users.toLocaleString()}
          icon={UsersIcon}
          color="blue"
        />
        <MetricCard
          title="Active Users (30d)"
          value={stats.active_users.toLocaleString()}
          icon={PlayIcon}
          color="green"
        />
        <MetricCard
          title="Total Agents"
          value={stats.total_agents.toLocaleString()}
          icon={MicrophoneIcon}
          color="purple"
        />
        <MetricCard
          title="Calls (30d)"
          value={stats.total_calls_30d.toLocaleString()}
          icon={PhoneIcon}
          color="orange"
        />
      </div>

      {/* Secondary Metrics */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Calls/Min (1h avg)"
          value={stats.calls_per_minute.toFixed(1)}
          icon={ChartBarIcon}
          color="indigo"
        />
        <MetricCard
          title="Queue Depth"
          value={stats.queue_depth.toLocaleString()}
          icon={ExclamationTriangleIcon}
          color="yellow"
        />
        <MetricCard
          title="Monthly Revenue"
          value={formatCurrency(stats.monthly_revenue)}
          icon={CurrencyDollarIcon}
          color="emerald"
        />
        <MetricCard
          title="Platform Health"
          value="Operational"
          icon={ShieldCheckIcon}
          color="green"
        />
      </div>

      {/* Quick Actions */}
      <div className="card">
        <div className="card-header">
          <h2 className="text-lg font-semibold text-gray-900">Quick Actions</h2>
        </div>
        <div className="card-body grid gap-4 md:grid-cols-3">
          <QuickActionButton
            title="View All Users"
            description="Manage user accounts, suspensions"
            icon={UsersIcon}
            onClick={() => window.location.hash = '#users'}
          />
          <QuickActionButton
            title="View All Agents"
            description="Monitor agent configurations"
            icon={MicrophoneIcon}
            onClick={() => window.location.hash = '#agents'}
          />
          <QuickActionButton
            title="Audit Logs"
            description="Review security and admin actions"
            icon={DocumentTextIcon}
            onClick={() => window.location.hash = '#audit'}
          />
        </div>
      </div>
    </div>
  );
}

function MetricCard({
  title,
  value,
  icon: Icon,
  color,
}: {
  title: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
}) {
  const colors: Record<string, string> = {
    blue: 'bg-blue-100 text-blue-600',
    green: 'bg-green-100 text-green-600',
    purple: 'bg-purple-100 text-purple-600',
    orange: 'bg-orange-100 text-orange-600',
    indigo: 'bg-indigo-100 text-indigo-600',
    yellow: 'bg-yellow-100 text-yellow-600',
    emerald: 'bg-emerald-100 text-emerald-600',
  };

  return (
    <div className="card">
      <div className="card-body">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-500">{title}</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">{value}</p>
          </div>
          <div className={`p-3 rounded-xl ${colors[color] || colors.blue}`}>
            <Icon className="w-6 h-6" />
          </div>
        </div>
      </div>
    </div>
  );
}

function QuickActionButton({
  title,
  description,
  icon: Icon,
  onClick,
}: {
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="card-body text-left hover:bg-gray-50 transition-colors"
    >
      <div className="flex items-center space-x-4">
        <div className="p-3 bg-primary-100 text-primary-600 rounded-xl">
          <Icon className="w-6 h-6" />
        </div>
        <div>
          <h3 className="font-semibold text-gray-900">{title}</h3>
          <p className="text-sm text-gray-500">{description}</p>
        </div>
      </div>
    </button>
  );
}

function UsersTab({
  users,
  loading,
  page,
  setPage,
  search,
  setSearch,
  onSuspend,
}: {
  users: AdminUser[];
  loading: boolean;
  page: number;
  setPage: (page: number) => void;
  search: string;
  setSearch: (search: string) => void;
  onSuspend: (userId: string, email: string, suspend: boolean) => void;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">User Management</h2>
        <div className="relative">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            type="text"
            placeholder="Search users..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="input pl-10 w-64"
          />
        </div>
      </div>

      {loading ? (
        <div className="card card-body flex items-center justify-center h-40">
          <div className="animate-spin rounded-full h-8 w-8 border-4 border-primary-600 border-t-transparent"></div>
        </div>
      ) : users.length === 0 ? (
        <div className="card card-body text-center py-12">
          <UsersIcon className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500">No users found</p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Plan</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Agents</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Subscription</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Joined</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {users.map((user) => (
                <tr key={user.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div>
                      <p className="font-medium text-gray-900">{user.email}</p>
                      <p className="text-sm text-gray-500">{user.id.slice(0, 8)}...</p>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`badge ${getPlanBadge(user.plan)}`}>{user.plan}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={user.is_active ? 'text-green-600' : 'text-red-600'}>
                      {user.is_active ? 'Active' : 'Suspended'}
                    </span>
                    {!user.is_verified && (
                      <span className="ml-2 badge badge-yellow text-xs">Unverified</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-900">{user.agent_count}</td>
                  <td className="px-4 py-3">
                    {user.subscription_status ? (
                      <span className={`badge ${user.subscription_status === 'active' ? 'badge-success' : 'badge-warning'}`}>
                        {user.subscription_plan} ({user.subscription_status})
                      </span>
                    ) : (
                      <span className="text-gray-400">None</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {formatDate(user.created_at)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {user.is_active ? (
                      <button
                        onClick={() => onSuspend(user.id, user.email, true)}
                        className="btn-ghost text-red-600 text-sm"
                      >
                        <PauseIcon className="w-4 h-4" />
                        Suspend
                      </button>
                    ) : (
                      <button
                        onClick={() => onSuspend(user.id, user.email, false)}
                        className="btn-ghost text-green-600 text-sm"
                      >
                        <PlayIcon className="w-4 h-4" />
                        Unsuspend
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {users.length === pageSize && (
        <div className="flex items-center justify-center space-x-2">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            className="btn-secondary"
          >
            Previous
          </button>
          <span className="px-4 text-sm text-gray-700">Page {page}</span>
          <button
            onClick={() => setPage(p => p + 1)}
            className="btn-secondary"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

function AgentsTab({
  agents,
  loading,
  page,
  setPage,
  statusFilter,
  setStatusFilter,
}: {
  agents: AdminAgent[];
  loading: boolean;
  page: number;
  setPage: (page: number) => void;
  statusFilter: string;
  setStatusFilter: (filter: string) => void;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">All Agents</h2>
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="input w-48"
        >
          <option value="">All Statuses</option>
          <option value="draft">Draft</option>
          <option value="active">Active</option>
          <option value="paused">Paused</option>
          <option value="archived">Archived</option>
        </select>
      </div>

      {loading ? (
        <div className="card card-body flex items-center justify-center h-40">
          <div className="animate-spin rounded-full h-8 w-8 border-4 border-primary-600 border-t-transparent"></div>
        </div>
      ) : agents.length === 0 ? (
        <div className="card card-body text-center py-12">
          <MicrophoneIcon className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500">No agents found</p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Agent</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Owner</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Direction</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Updated</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {agents.map((agent) => (
                <tr key={agent.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <p className="font-medium text-gray-900">{agent.name}</p>
                    <p className="text-sm text-gray-500">{agent.id.slice(0, 8)}...</p>
                  </td>
                  <td className="px-4 py-3">
                    <p className="text-sm text-gray-900">{agent.owner_email}</p>
                    <p className="text-xs text-gray-500">{agent.owner_id.slice(0, 8)}...</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className="badge badge-info capitalize">{agent.direction}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`badge ${getStatusBadge(agent.status)}`}>{agent.status}</span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">{formatDate(agent.created_at)}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{formatDate(agent.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {agents.length === pageSize && (
        <div className="flex items-center justify-center space-x-2">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="btn-secondary">Previous</button>
          <span className="px-4 text-sm text-gray-700">Page {page}</span>
          <button onClick={() => setPage(p => p + 1)} className="btn-secondary">Next</button>
        </div>
      )}
    </div>
  );
}

function AuditTab({
  logs,
  loading,
  page,
  setPage,
  actionFilter,
  setActionFilter,
}: {
  logs: AuditLog[];
  loading: boolean;
  page: number;
  setPage: (page: number) => void;
  actionFilter: string;
  setActionFilter: (filter: string) => void;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Audit Logs</h2>
        <input
          type="text"
          placeholder="Filter by action..."
          value={actionFilter}
          onChange={(e) => { setActionFilter(e.target.value); setPage(1); }}
          className="input w-64"
        />
      </div>

      {loading ? (
        <div className="card card-body flex items-center justify-center h-40">
          <div className="animate-spin rounded-full h-8 w-8 border-4 border-primary-600 border-t-transparent"></div>
        </div>
      ) : logs.length === 0 ? (
        <div className="card card-body text-center py-12">
          <DocumentTextIcon className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500">No audit logs found</p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Resource</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">IP</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {logs.map((log) => (
                <tr key={log.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm text-gray-500">{formatDate(log.created_at)}</td>
                  <td className="px-4 py-3">
                    <span className="font-mono text-sm text-gray-900">{log.action}</span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">{log.user_id ? log.user_id.slice(0, 8) + '...' : 'System'}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {log.resource_type ? `${log.resource_type}:${log.resource_id?.slice(0, 8)}...` : 'N/A'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500 font-mono">{log.ip_address || 'N/A'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {logs.length === pageSize && (
        <div className="flex items-center justify-center space-x-2">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="btn-secondary">Previous</button>
          <span className="px-4 text-sm text-gray-700">Page {page}</span>
          <button onClick={() => setPage(p => p + 1)} className="btn-secondary">Next</button>
        </div>
      )}
    </div>
  );
}

function SettingsTab() {
  return (
    <div className="space-y-6">
      <div className="card">
        <div className="card-header">
          <h2 className="text-lg font-semibold text-gray-900">Admin Settings</h2>
        </div>
        <div className="card-body space-y-6">
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <div className="flex items-center space-x-3">
              <ExclamationTriangleIcon className="w-6 h-6 text-yellow-600" />
              <div>
                <h3 className="font-semibold text-yellow-800">IP Restriction Not Configured</h3>
                <p className="text-yellow-700 text-sm mt-1">
                  Admin panel access is not restricted by IP. Configure <code>ADMIN_ALLOWED_IPS</code> in your environment variables
                  to restrict access to specific IP ranges (CIDR notation).
                </p>
              </div>
            </div>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            <div className="bg-gray-50 rounded-lg p-4">
              <h4 className="font-semibold text-gray-900 mb-3">Admin Access Configuration</h4>
              <dl className="space-y-2 text-sm">
                <dt className="text-gray-500">ADMIN_ALLOWED_IPS</dt>
                <dd className="font-mono bg-gray-100 px-2 py-1 rounded">Comma-separated CIDR blocks (e.g., "192.168.1.0/24,10.0.0.0/8")</dd>
                <dt className="text-gray-500">Current Value</dt>
                <dd className="font-mono bg-gray-100 px-2 py-1 rounded text-red-600">Not set (open access)</dd>
              </dl>
            </div>

            <div className="bg-gray-50 rounded-lg p-4">
              <h4 className="font-semibold text-gray-900 mb-3">Security Recommendations</h4>
              <ul className="space-y-2 text-sm text-gray-600">
                <li className="flex items-center space-x-2"><ShieldCheckIcon className="w-5 h-5 text-green-500" /><span>Enable IP restriction for production</span></li>
                <li className="flex items-center space-x-2"><ShieldCheckIcon className="w-5 h-5 text-green-500" /><span>Use VPN/bastion for admin access</span></li>
                <li className="flex items-center space-x-2"><ShieldCheckIcon className="w-5 h-5 text-green-500" /><span>Enable MFA for admin accounts</span></li>
                <li className="flex items-center space-x-2"><ShieldCheckIcon className="w-5 h-5 text-green-500" /><span>Regular audit log review</span></li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleString();
}

function formatCurrency(amount: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount);
}

function getPlanBadge(plan: string) {
  const badges: Record<string, string> = {
    free: 'badge-gray',
    starter: 'badge-blue',
    pro: 'badge-purple',
    enterprise: 'badge-gold',
  };
  return badges[plan] || 'badge-gray';
}

function getStatusBadge(status: string) {
  const badges: Record<string, string> = {
    active: 'badge-success',
    inactive: 'badge-gray',
    draft: 'badge-gray',
    paused: 'badge-warning',
    archived: 'badge-info',
  };
  return badges[status] || 'badge-gray';
}