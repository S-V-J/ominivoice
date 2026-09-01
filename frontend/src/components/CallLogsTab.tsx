import { useEffect, useState } from 'react';
import { api } from '../services/api';
import type { Agent } from '../types';
import {
  MagnifyingGlassIcon,
  FunnelIcon,
  ArrowPathIcon,
  PlayIcon,
  DownloadIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  DocumentTextIcon,
  SpeakerWaveIcon,
} from '@heroicons/react/24/outline';

interface CallLog {
  id: string;
  agent_id: string;
  direction: 'inbound' | 'outbound';
  caller_ref: string | null;
  transcript: Array<{
    turn_id: string;
    role: 'user' | 'assistant';
    text: string;
    timestamp: string;
    duration_ms: number;
    interrupted: boolean;
    metadata: Record<string, any>;
  }>;
  duration_s: number;
  status: string;
  started_at: string;
  ended_at: string | null;
  error_message: string | null;
}

interface CallLogsResponse {
  calls: CallLog[];
  total: number;
  page: number;
  page_size: number;
}

export default function CallLogsTab({ agent }: { agent: Agent }) {
  const [calls, setCalls] = useState<CallLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState({
    status: '',
    direction: '',
    start_date: '',
    end_date: '',
    search: '',
  });
  const [selectedCall, setSelectedCall] = useState<CallLog | null>(null);
  const [showTranscriptModal, setShowTranscriptModal] = useState(false);

  useEffect(() => {
    loadCalls();
  }, [page, filters]);

  const loadCalls = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {
        limit: pageSize,
        offset: (page - 1) * pageSize,
        status: filters.status || undefined,
        direction: filters.direction || undefined,
        start_date: filters.start_date || undefined,
        end_date: filters.end_date || undefined,
      };
      const response = await api.get(`/agents/${agent.id}/calls`, { params });
      // Handle both array response and paginated response
      if (Array.isArray(response)) {
        setCalls(response);
        setTotal(response.length);
      } else {
        setCalls(response.calls || response);
        setTotal(response.total || response.length);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load call logs');
      console.error('Failed to load calls:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (key: string, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  const getStatusBadge = (status: string) => {
    const badges: Record<string, string> = {
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
      in_progress: 'bg-yellow-100 text-yellow-800',
      answered: 'bg-blue-100 text-blue-800',
      initiated: 'bg-gray-100 text-gray-800',
      busy: 'bg-orange-100 text-orange-800',
      no_answer: 'bg-gray-100 text-gray-800',
      voicemail: 'bg-purple-100 text-purple-800',
      queued_for_external_dialer: 'bg-indigo-100 text-indigo-800',
    };
    return badges[status] || 'bg-gray-100 text-gray-800';
  };

  const getDirectionIcon = (direction: string) => {
    return direction === 'outbound' ? (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" /></svg>
    ) : (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16l-4-4m0 0l4-4m-4 4h18" /></svg>
    );
  };

  const handleViewTranscript = (call: CallLog) => {
    setSelectedCall(call);
    setShowTranscriptModal(true);
  };

  const handleExportCSV = async () => {
    try {
      const response = await api.get(`/agents/${agent.id}/calls`, {
        params: { ...filters, limit: 10000, offset: 0 },
      });
      const allCalls = Array.isArray(response) ? response : (response.calls || response);

      const headers = ['Call ID', 'Direction', 'Caller', 'Status', 'Duration', 'Started', 'Ended', 'Transcript Preview'];
      const rows = allCalls.map(call => [
        call.id.slice(0, 8),
        call.direction,
        call.caller_ref || 'Unknown',
        call.status,
        formatDuration(call.duration_s),
        formatDate(call.started_at),
        call.ended_at ? formatDate(call.ended_at) : 'N/A',
        call.transcript.map(t => `${t.role}: ${t.text.slice(0, 50)}`).join(' | '),
      ]);

      const csvContent = [headers.join(','), ...rows.map(r => r.map(c => `"${c}"`).join(','))].join('\n');
      const blob = new Blob([csvContent], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `call-logs-${agent.name}-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
    }
  };

  if (loading && calls.length === 0) {
    return (
      <div className="card card-body flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary-600 border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with Filters */}
      <div className="card">
        <div className="card-header flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Call Logs</h2>
            <p className="text-sm text-gray-500 mt-1">View and manage call history for {agent.name}</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={loadCalls}
              disabled={loading}
              className="btn-secondary flex items-center gap-2"
            >
              <ArrowPathIcon className="w-4 h-4" />
              Refresh
            </button>
            <button
              onClick={handleExportCSV}
              className="btn-secondary flex items-center gap-2"
            >
              <DownloadIcon className="w-4 h-4" />
              Export CSV
            </button>
          </div>
        </div>
        <div className="card-body">
          {/* Filter Row */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5 mb-4">
            <div className="relative">
              <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search transcript..."
                value={filters.search}
                onChange={(e) => handleFilterChange('search', e.target.value)}
                className="input pl-10"
              />
            </div>
            <select
              value={filters.status}
              onChange={(e) => handleFilterChange('status', e.target.value)}
              className="input"
            >
              <option value="">All Statuses</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="in_progress">In Progress</option>
              <option value="answered">Answered</option>
              <option value="initiated">Initiated</option>
              <option value="busy">Busy</option>
              <option value="no_answer">No Answer</option>
              <option value="voicemail">Voicemail</option>
              <option value="queued_for_external_dialer">Queued for External Dialer</option>
            </select>
            <select
              value={filters.direction}
              onChange={(e) => handleFilterChange('direction', e.target.value)}
              className="input"
            >
              <option value="">All Directions</option>
              <option value="outbound">Outbound</option>
              <option value="inbound">Inbound</option>
            </select>
            <input
              type="date"
              value={filters.start_date}
              onChange={(e) => handleFilterChange('start_date', e.target.value)}
              className="input"
              placeholder="Start Date"
            />
            <input
              type="date"
              value={filters.end_date}
              onChange={(e) => handleFilterChange('end_date', e.target.value)}
              className="input"
              placeholder="End Date"
            />
          </div>

          {/* Call Logs Table */}
          {error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 mb-4">
              {error}
            </div>
          )}

          {calls.length === 0 ? (
            <div className="text-center py-12">
              <DocumentTextIcon className="w-12 h-12 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No call logs found</h3>
              <p className="text-gray-500">Make a call or process queue entries to see logs here.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Call</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Direction</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Caller</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Duration</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Started</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Transcript</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {calls.map((call) => (
                    <tr key={call.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <span className="font-mono text-sm text-gray-500">{call.id.slice(0, 8)}...</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="flex items-center gap-1 text-sm">
                          {getDirectionIcon(call.direction)}
                          <span className="capitalize">{call.direction}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-sm text-gray-900 font-mono">{call.caller_ref || 'Unknown'}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${getStatusBadge(call.status)}`}>
                          {call.status.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-sm font-mono text-gray-900">{formatDuration(call.duration_s)}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-sm text-gray-500">{formatDate(call.started_at)}</span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="max-w-xs truncate text-sm text-gray-600">
                          {call.transcript.length > 0
                            ? call.transcript.slice(0, 2).map(t => `${t.role === 'assistant' ? '🤖' : '👤'} ${t.text.slice(0, 60)}`).join(' → ')
                            : 'No transcript'}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => handleViewTranscript(call)}
                          className="btn-ghost text-sm flex items-center gap-1"
                        >
                          <DocumentTextIcon className="w-4 h-4" />
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {total > pageSize && (
            <div className="flex items-center justify-between mt-4">
              <div className="text-sm text-gray-500">
                Showing {Math.min((page - 1) * pageSize + 1, total)} to {Math.min(page * pageSize, total)} of {total} calls
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="btn-secondary p-2"
                >
                  <ChevronLeftIcon className="w-5 h-5" />
                </button>
                <span className="px-3 text-sm text-gray-700">
                  Page {page} of {Math.ceil(total / pageSize)}
                </span>
                <button
                  onClick={() => setPage(p => Math.min(Math.ceil(total / pageSize), p + 1))}
                  disabled={page >= Math.ceil(total / pageSize)}
                  className="btn-secondary p-2"
                >
                  <ChevronRightIcon className="w-5 h-5" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Transcript Modal */}
      {showTranscriptModal && selectedCall && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" onClick={() => setShowTranscriptModal(false)}>
          <div className="bg-white rounded-xl max-w-3xl w-full max-h-[80vh] overflow-hidden" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b border-gray-200">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Call Transcript</h3>
                <p className="text-sm text-gray-500">
                  {selectedCall.direction} • {formatDuration(selectedCall.duration_s)} • {formatDate(selectedCall.started_at)}
                </p>
              </div>
              <button onClick={() => setShowTranscriptModal(false)} className="text-gray-400 hover:text-gray-600">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <div className="p-4 max-h-[60vh] overflow-y-auto">
              {selectedCall.transcript.length === 0 ? (
                <p className="text-gray-500 text-center py-8">No transcript available</p>
              ) : (
                <div className="space-y-4">
                  {selectedCall.transcript.map((turn, idx) => (
                    <div key={`${turn.turn_id}-${idx}`} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex items-baseline justify-between mb-2">
                        <span className={`font-medium text-sm ${turn.role === 'assistant' ? 'text-green-700' : 'text-blue-700'}`}>
                          {turn.role === 'assistant' ? '🤖 Agent' : '👤 User'}
                        </span>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-500">{new Date(turn.timestamp).toLocaleTimeString()}</span>
                          {turn.interrupted && (
                            <span className="text-xs text-red-600 bg-red-50 px-2 py-0.5 rounded">INTERRUPTED</span>
                          )}
                          <span className="text-xs text-gray-500">({turn.duration_ms}ms)</span>
                        </div>
                      </div>
                      <p className="text-gray-800 whitespace-pre-wrap">{turn.text}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="flex justify-end gap-2 p-4 border-t border-gray-200">
              <button onClick={() => setShowTranscriptModal(false)} className="btn-secondary">
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}