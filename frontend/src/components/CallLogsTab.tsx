import { useEffect, useState } from 'react';
import { api } from '../services/api';
import type { CallLog, CallLogStats, Agent } from '../types';
import { DocumentTextIcon, PlayIcon, ClockIcon, CheckCircleIcon, XCircleIcon } from '@heroicons/react/24/outline';

export default function CallLogsTab({ agent }: { agent: Agent }) {
  const [logs, setLogs] = useState<CallLog[]>([]);
  const [stats, setStats] = useState<CallLogStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedLog, setSelectedLog] = useState<CallLog | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [filters, setFilters] = useState({
    status: '',
    direction: '',
    start_date: '',
    end_date: '',
  });

  useEffect(() => {
    loadLogs();
    loadStats();
  }, [agent.id, page, filters]);

  const loadLogs = async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {
        limit: '20',
        offset: String((page - 1) * 20),
      };
      if (filters.status) params.status = filters.status;
      if (filters.direction) params.direction = filters.direction;
      if (filters.start_date) params.start_date = filters.start_date;
      if (filters.end_date) params.end_date = filters.end_date;

      const data = await api.get(`/agents/${agent.id}/calls`, { params });
      setLogs(data);
      setTotalPages(Math.ceil(data.length / 20)); // Approximation
    } catch (err: any) {
      console.error('Failed to load call logs:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const params: Record<string, string> = {};
      if (filters.start_date) params.start_date = filters.start_date;
      if (filters.end_date) params.end_date = filters.end_date;

      const data = await api.get(`/agents/${agent.id}/calls/stats`, { params });
      setStats(data);
    } catch (err) {
      console.error('Failed to load call stats:', err);
    }
  };

  const handleFilterChange = (key: string, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getStatusBadge = (status: string) => {
    const badges: Record<string, string> = {
      completed: 'badge-success',
      failed: 'badge-danger',
      in_progress: 'badge-warning',
      answered: 'badge-info',
      ringing: 'badge-gray',
      initiated: 'badge-gray',
      busy: 'badge-warning',
      no_answer: 'badge-gray',
      voicemail: 'badge-info',
      queued_for_external_dialer: 'badge-info',
    };
    return badges[status] || 'badge-gray';
  };

  const getStatusIcon = (status: string) => {
    if (status === 'completed') return <CheckCircleIcon className="w-5 h-5 text-green-500" />;
    if (status === 'failed') return <XCircleIcon className="w-5 h-5 text-red-500" />;
    if (status === 'in_progress' || status === 'answered') return <PlayIcon className="w-5 h-5 text-blue-500" />;
    return <ClockIcon className="w-5 h-5 text-gray-400" />;
  };

  const handleViewLog = (log: CallLog) => {
    setSelectedLog(log);
  };

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      {stats && (
        <div className="grid gap-4 md:grid-cols-4">
          <StatCard label="Total Calls" value={stats.total_calls} icon={<DocumentTextIcon className="w-5 h-5" />} color="gray" />
          <StatCard label="Completed" value={stats.completed} icon={<CheckCircleIcon className="w-5 h-5" />} color="green" />
          <StatCard label="Failed" value={stats.failed} icon={<XCircleIcon className="w-5 h-5" />} color="red" />
          <StatCard label="Success Rate" value={`${stats.success_rate}%`} icon={<ClockIcon className="w-5 h-5" />} color="blue" />
        </div>
      )}

      {/* Filters */}
      <div className="card">
        <div className="card-body">
          <div className="flex flex-wrap gap-4">
            <div className="flex-1 min-w-[200px]">
              <label className="label">Status</label>
              <select
                value={filters.status}
                onChange={(e) => handleFilterChange('status', e.target.value)}
                className="input"
              >
                <option value="">All Status</option>
                <option value="completed">Completed</option>
                <option value="failed">Failed</option>
                <option value="in_progress">In Progress</option>
                <option value="answered">Answered</option>
                <option value="ringing">Ringing</option>
                <option value="initiated">Initiated</option>
                <option value="busy">Busy</option>
                <option value="no_answer">No Answer</option>
                <option value="voicemail">Voicemail</option>
                <option value="queued_for_external_dialer">Queued for Dialer</option>
              </select>
            </div>
            <div className="flex-1 min-w-[200px]">
              <label className="label">Direction</label>
              <select
                value={filters.direction}
                onChange={(e) => handleFilterChange('direction', e.target.value)}
                className="input"
              >
                <option value="">All Directions</option>
                <option value="inbound">Inbound</option>
                <option value="outbound">Outbound</option>
              </select>
            </div>
            <div className="flex-1 min-w-[200px]">
              <label className="label">Start Date</label>
              <input
                type="date"
                value={filters.start_date}
                onChange={(e) => handleFilterChange('start_date', e.target.value)}
                className="input"
              />
            </div>
            <div className="flex-1 min-w-[200px]">
              <label className="label">End Date</label>
              <input
                type="date"
                value={filters.end_date}
                onChange={(e) => handleFilterChange('end_date', e.target.value)}
                className="input"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Call Logs Table */}
      <div className="card overflow-hidden">
        {loading ? (
          <div className="card-body flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-4 border-primary-600 border-t-transparent"></div>
          </div>
        ) : logs.length === 0 ? (
          <div className="card-body text-center py-12">
            <DocumentTextIcon className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <h3 className="text-lg font-medium text-gray-900 mb-1">No call logs found</h3>
            <p className="text-gray-500">Calls will appear here after test calls or queue processing</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Direction</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Duration</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Caller</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {logs.map((log) => (
                    <tr key={log.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => handleViewLog(log)}>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {new Date(log.started_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          log.direction === 'inbound' ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800'
                        }`}>
                          {log.direction}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center ${getStatusBadge(log.status)}`}>
                          {getStatusIcon(log.status)}
                          <span className="ml-1 capitalize">{log.status.replace('_', ' ')}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500">
                        {log.duration_s ? formatDuration(log.duration_s) : '—'}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500 font-mono">
                        {log.caller_ref || '—'}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={(e) => { e.stopPropagation(); handleViewLog(log); }}
                          className="btn-ghost text-sm"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="card-body flex items-center justify-between border-t border-gray-200">
              <p className="text-sm text-gray-500">
                Page {page} of {totalPages || 1}
              </p>
              <div className="flex space-x-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="btn-secondary"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage(p => Math.min((totalPages || 1), p + 1))}
                  disabled={page >= (totalPages || 1)}
                  className="btn-secondary"
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Call Detail Modal */}
      {selectedLog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => setSelectedLog(null)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-3xl max-h-[80vh] overflow-y-auto mx-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-gray-900">Call Details</h3>
              <button onClick={() => setSelectedLog(null)} className="text-gray-400 hover:text-gray-600">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/></svg>
              </button>
            </div>

            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="label">Call ID</label>
                  <p className="font-mono text-sm text-gray-700 break-all">{selectedLog.id}</p>
                </div>
                <div>
                  <label className="label">Agent ID</label>
                  <p className="font-mono text-sm text-gray-700 break-all">{selectedLog.agent_id}</p>
                </div>
                <div>
                  <label className="label">Direction</label>
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    selectedLog.direction === 'inbound' ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800'
                  }`}>
                    {selectedLog.direction}
                  </span>
                </div>
                <div>
                  <label className="label">Status</label>
                  <span className={`inline-flex items-center ${getStatusBadge(selectedLog.status)}`}>
                    {getStatusIcon(selectedLog.status)}
                    <span className="ml-1 capitalize">{selectedLog.status.replace('_', ' ')}</span>
                  </span>
                </div>
                <div>
                  <label className="label">Duration</label>
                  <p className="text-gray-700">{selectedLog.duration_s ? formatDuration(selectedLog.duration_s) : '—'}</p>
                </div>
                <div>
                  <label className="label">Caller</label>
                  <p className="font-mono text-sm text-gray-700">{selectedLog.caller_ref || '—'}</p>
                </div>
                <div>
                  <label className="label">Started</label>
                  <p className="text-gray-700">{new Date(selectedLog.started_at).toLocaleString()}</p>
                </div>
                <div>
                  <label className="label">Ended</label>
                  <p className="text-gray-700">{selectedLog.ended_at ? new Date(selectedLog.ended_at).toLocaleString() : '—'}</p>
                </div>
              </div>

              {selectedLog.error_message && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <label className="label text-red-700">Error Message</label>
                  <p className="text-red-600">{selectedLog.error_message}</p>
                </div>
              )}

              <div>
                <label className="label">Transcript</label>
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 max-h-96 overflow-y-auto">
                  {selectedLog.transcript && selectedLog.transcript.length > 0 ? (
                    <div className="space-y-3">
                      {selectedLog.transcript.map((turn: any, idx: number) => (
                        <div key={idx} className="flex flex-col space-y-1">
                          <div className="flex items-baseline space-x-2">
                            <span className={`font-medium text-sm ${turn.role === 'assistant' ? 'text-green-700' : 'text-blue-700'}`}>
                              {turn.role === 'assistant' ? 'Agent' : 'User'}
                            </span>
                            <span className="text-xs text-gray-500">
                              {turn.timestamp ? new Date(turn.timestamp).toLocaleTimeString() : ''}
                            </span>
                            {turn.interrupted && (
                              <span className="text-xs text-red-600 bg-red-50 px-1.5 py-0.5 rounded">INTERRUPTED</span>
                            )}
                          </div>
                          <p className="text-gray-800 ml-6">{turn.text}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-gray-500 text-center py-8">No transcript available</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, icon, color }: { label: string; value: number | string; icon: React.ReactNode; color: string }) {
  const colors: Record<string, string> = {
    gray: 'bg-gray-100 text-gray-600',
    blue: 'bg-blue-100 text-blue-600',
    green: 'bg-green-100 text-green-600',
    red: 'bg-red-100 text-red-600',
  };

  return (
    <div className={`card p-4 ${colors[color] || colors.gray} rounded-lg`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium">{label}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
        </div>
        <div className="w-10 h-10 rounded-lg flex items-center justify-center opacity-80">
          {icon}
        </div>
      </div>
    </div>
  );
}