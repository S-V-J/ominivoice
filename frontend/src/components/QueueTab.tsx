import { useEffect, useState } from 'react';
import { api } from '../services/api';
import toast from 'react-hot-toast';
import type { Agent, ColdCallQueueEntry, QueueEntryStatus, ColdCallQueueStats } from '../types';
import {
  DocumentArrowUpIcon,
  FunnelIcon,
  ArrowPathIcon,
  TrashIcon,
  ArrowDownTrayIcon,
  ChartBarIcon,
  CheckIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from 'recharts';

const STATUS_BADGES: Record<QueueEntryStatus, string> = {
  pending: 'badge-gray',
  queued: 'badge-info',
  in_progress: 'badge-warning',
  completed: 'badge-success',
  failed: 'badge-danger',
};

const STATUS_LABELS: Record<QueueEntryStatus, string> = {
  pending: 'Pending',
  queued: 'Queued',
  in_progress: 'In Progress',
  completed: 'Completed',
  failed: 'Failed',
};

export default function QueueTab({ agent }: { agent: Agent }) {
  const [entries, setEntries] = useState<ColdCallQueueEntry[]>([]);
  const [stats, setStats] = useState<ColdCallQueueStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importSource, setImportSource] = useState('csv_upload');
  const [statusFilter, setStatusFilter] = useState<QueueEntryStatus | 'all'>('all');
  const [sortBy, setSortBy] = useState<'created_at' | 'scheduled_at' | 'contact_name' | 'status'>('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  // Bulk actions
  const [selectedEntries, setSelectedEntries] = useState<Set<string>>(new Set());
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [scheduleEntry, setScheduleEntry] = useState<ColdCallQueueEntry | null>(null);
  const [scheduleDate, setScheduleDate] = useState('');
  const [scheduleTime, setScheduleTime] = useState('');

  useEffect(() => {
    loadData();
  }, [agent.id, statusFilter, sortBy, sortOrder]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [entriesData, statsData] = await Promise.all([
        api.listQueueEntries(agent.id, { status: statusFilter !== 'all' ? statusFilter : undefined, sort_by: sortBy, sort_order: sortOrder }),
        api.getQueueStats(agent.id),
      ]);
      setEntries(entriesData);
      setStats(statsData);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to load queue');
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setImportFile(e.target.files[0]);
    }
  };

  const handleImport = async () => {
    if (!importFile) {
      toast.error('Please select a CSV file');
      return;
    }

    setImporting(true);
    try {
      const result = await api.importQueue(agent.id, importFile, importSource);
      toast.success(`Imported ${result.created} entries, skipped ${result.skipped_duplicates} duplicates`);
      if (result.errors > 0) {
        toast.error(`${result.errors} entries had errors`);
      }
      setShowImportModal(false);
      setImportFile(null);
      loadData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Import failed');
    } finally {
      setImporting(false);
    }
  };

  const handleRetryFailed = async () => {
    try {
      const result = await api.retryFailedQueueEntries(agent.id);
      toast.success(`Retrying ${result.retried} failed entries`);
      loadData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Retry failed');
    }
  };

  const handleStatusChange = async (entry: ColdCallQueueEntry, newStatus: QueueEntryStatus) => {
    try {
      await api.updateQueueEntry(agent.id, entry.id, { status: newStatus });
      toast.success('Status updated');
      loadData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update status');
    }
  };

  const handleDelete = async (entry: ColdCallQueueEntry) => {
    if (!confirm(`Delete ${entry.contact_name} (${entry.phone_number})?`)) return;
    try {
      await api.deleteQueueEntry(agent.id, entry.id);
      toast.success('Entry deleted');
      loadData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to delete');
    }
  };

  const handleBulkDelete = async () => {
    if (!confirm(`Delete ${selectedEntries.size} entries?`)) return;
    try {
      for (const entryId of selectedEntries) {
        await api.deleteQueueEntry(agent.id, entryId);
      }
      toast.success(`${selectedEntries.size} entries deleted`);
      setSelectedEntries(new Set());
      loadData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to delete');
    }
  };

  const handleBulkRetry = async () => {
    if (!confirm(`Retry ${selectedEntries.size} failed entries?`)) return;
    try {
      for (const entryId of selectedEntries) {
        await api.updateQueueEntry(agent.id, entryId, { status: 'pending' as QueueEntryStatus });
      }
      toast.success(`${selectedEntries.size} entries queued for retry`);
      setSelectedEntries(new Set());
      loadData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to retry');
    }
  };

  const handleExportSelected = () => {
    const selected = entries.filter(e => selectedEntries.has(e.id));
    if (selected.length === 0) return;

    const headers = ['Contact Name', 'Phone Number', 'Status', 'Source', 'Created', 'Payload'];
    const rows = selected.map(e => [
      e.contact_name,
      e.phone_number,
      e.status,
      e.source,
      new Date(e.created_at).toLocaleString(),
      JSON.stringify(e.payload || {}),
    ]);

    const csvContent = [headers.join(','), ...rows.map(r => r.map(c => `"${c}"`).join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `queue-export-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleScheduleClick = (entry: ColdCallQueueEntry) => {
    setScheduleEntry(entry);
    setShowScheduleModal(true);
  };

  const handleScheduleSave = async () => {
    if (!scheduleEntry || !scheduleDate || !scheduleTime) return;
    try {
      const scheduledAt = new Date(`${scheduleDate}T${scheduleTime}:00`).toISOString();
      await api.updateQueueEntry(agent.id, scheduleEntry.id, { scheduled_at: scheduledAt });
      toast.success('Call scheduled');
      setShowScheduleModal(false);
      setScheduleEntry(null);
      loadData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to schedule');
    }
  };

  const handleSort = (column: 'created_at' | 'scheduled_at' | 'contact_name' | 'status') => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortOrder('asc');
    }
  };

  const handleSelectionChange = (entryId: string, checked: boolean) => {
    const newSelected = new Set(selectedEntries);
    if (checked) {
      newSelected.add(entryId);
    } else {
      newSelected.delete(entryId);
    }
    setSelectedEntries(newSelected);
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedEntries(new Set(entries.map(e => e.id)));
    } else {
      setSelectedEntries(new Set());
    }
  };

  const downloadCSVTemplate = () => {
    const csv = 'contact_name,phone_number,email,company\nJohn Doe,+15551234567,john@example.com,Acme Corp\nJane Smith,+15559876543,jane@example.com,Globex Inc\n';
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'queue_import_template.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  const getSortIcon = (column: string) => {
    if (sortBy !== column) return null;
    return sortOrder === 'asc' ? '↑' : '↓';
  };

  const chartData = stats ? [
    { name: 'Pending', value: stats.pending, color: '#9CA3AF' },
    { name: 'Queued', value: stats.queued, color: '#3B82F6' },
    { name: 'In Progress', value: stats.in_progress, color: '#F59E0B' },
    { name: 'Completed', value: stats.completed, color: '#10B981' },
    { name: 'Failed', value: stats.failed, color: '#EF4444' },
  ].filter(d => d.value > 0) : [];

  return (
    <div className="space-y-6">
      {/* Header with stats */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Cold Call Queue</h2>
          <p className="text-sm text-gray-500 mt-1">Manage outbound call contacts for this agent</p>
        </div>
        <div className="flex items-center space-x-3">
          <button onClick={downloadCSVTemplate} className="btn-secondary flex items-center space-x-2">
            <ArrowDownTrayIcon className="w-4 h-4" />
            <span>CSV Template</span>
          </button>
          <button onClick={() => setShowImportModal(true)} className="btn-primary flex items-center space-x-2">
            <DocumentArrowUpIcon className="w-4 h-4" />
            <span>Import CSV</span>
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid gap-4 md:grid-cols-5">
          <StatCard label="Total" value={stats.total} icon={<ChartBarIcon className="w-5 h-5" />} color="gray" />
          <StatCard label="Pending" value={stats.pending} icon={<ChartBarIcon className="w-5 h-5" />} color="gray" />
          <StatCard label="Queued" value={stats.queued} icon={<ChartBarIcon className="w-5 h-5" />} color="blue" />
          <StatCard label="Completed" value={stats.completed} icon={<ChartBarIcon className="w-5 h-5" />} color="green" />
          <StatCard label="Failed" value={stats.failed} icon={<ChartBarIcon className="w-5 h-5" />} color="red" />
        </div>
      )}

      {/* Status Distribution Chart */}
      {stats && chartData.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h3 className="text-lg font-semibold text-gray-900">Status Distribution</h3>
          </div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={chartData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={2}
                  dataKey="value"
                  nameKey="name"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  labelLine={false}
                >
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip formatter={(value: number) => [value.toString(), 'Entries']} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          {/* Bulk Actions */}
          {selectedEntries.size > 0 && (
            <div className="flex items-center space-x-2">
              <span className="text-sm text-gray-600">
                {selectedEntries.size} selected
              </span>
              <button onClick={handleExportSelected} className="btn-secondary text-sm flex items-center space-x-1">
                <ArrowDownTrayIcon className="w-4 h-4" />
                <span>Export</span>
              </button>
              <button onClick={handleBulkRetry} className="btn-secondary text-sm flex items-center space-x-1">
                <ArrowPathIcon className="w-4 h-4" />
                <span>Retry</span>
              </button>
              <button onClick={handleBulkDelete} className="btn-danger text-sm flex items-center space-x-1">
                <TrashIcon className="w-4 h-4" />
                <span>Delete</span>
              </button>
              <button onClick={() => setSelectedEntries(new Set())} className="btn-ghost text-sm">
                Clear
              </button>
            </div>
          )}

          {/* Status Filter */}
          <div className="relative">
            <FunnelIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as QueueEntryStatus | 'all')}
              className="input pl-10 pr-8 w-40"
            >
              <option value="all">All Status</option>
              <option value="pending">Pending</option>
              <option value="queued">Queued</option>
              <option value="in_progress">In Progress</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>
          </div>
        </div>
        <div className="flex items-center space-x-3">
          {stats?.failed && stats.failed > 0 && (
            <button onClick={handleRetryFailed} className="btn-secondary flex items-center space-x-2">
              <ArrowPathIcon className="w-4 h-4" />
              <span>Retry Failed ({stats.failed})</span>
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        {loading ? (
          <div className="card-body flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-4 border-primary-600 border-t-transparent"></div>
          </div>
        ) : entries.length === 0 ? (
          <div className="card-body text-center py-12">
            <DocumentArrowUpIcon className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <h3 className="text-lg font-medium text-gray-900 mb-1">No queue entries</h3>
            <p className="text-gray-500 mb-4">Import a CSV or add entries via API to get started</p>
            <button onClick={() => setShowImportModal(true)} className="btn-primary">
              <DocumentArrowUpIcon className="w-4 h-4 mr-2" />
              Import Contacts
            </button>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      <input
                        type="checkbox"
                        checked={selectedEntries.size === entries.length && entries.length > 0}
                        onChange={(e) => handleSelectAll(e.target.checked)}
                        className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                        aria-label="Select all"
                      />
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      <button onClick={() => handleSort('contact_name')} className="flex items-center space-x-1 hover:text-primary-600">
                        Contact <span className="text-xs">{getSortIcon('contact_name')}</span>
                      </button>
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      <button onClick={() => handleSort('contact_name')} className="flex items-center space-x-1 hover:text-primary-600">
                        Phone <span className="text-xs">{getSortIcon('contact_name')}</span>
                      </button>
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      <button onClick={() => handleSort('status')} className="flex items-center space-x-1 hover:text-primary-600">
                        Status <span className="text-xs">{getSortIcon('status')}</span>
                      </button>
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      <button onClick={() => handleSort('scheduled_at')} className="flex items-center space-x-1 hover:text-primary-600">
                        Scheduled <span className="text-xs">{getSortIcon('scheduled_at')}</span>
                      </button>
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      <button onClick={() => handleSort('created_at')} className="flex items-center space-x-1 hover:text-primary-600">
                        Added <span className="text-xs">{getSortIcon('created_at')}</span>
                      </button>
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {entries.map((entry) => (
                    <tr key={entry.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-center">
                        <input
                          type="checkbox"
                          checked={selectedEntries.has(entry.id)}
                          onChange={(e) => handleSelectionChange(entry.id, e.target.checked)}
                          className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                          aria-label={`Select ${entry.contact_name}`}
                        />
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-gray-900">{entry.contact_name}</div>
                        {entry.payload && Object.keys(entry.payload).length > 0 && (
                          <div className="text-xs text-gray-500 mt-1">
                            {Object.entries(entry.payload).map(([k, v]) => (
                              <span key={k} className="mr-2">{k}: {String(v)}</span>
                            ))}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-600 font-mono text-sm">{entry.phone_number}</td>
                      <td className="px-4 py-3">
                        <select
                          value={entry.status}
                          onChange={(e) => handleStatusChange(entry, e.target.value as QueueEntryStatus)}
                          className={`input w-28 ${STATUS_BADGES[entry.status]}`}
                        >
                          {Object.entries(STATUS_LABELS).map(([value, label]) => (
                            <option key={value} value={value}>{label}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-sm">
                        {entry.scheduled_at ? new Date(entry.scheduled_at).toLocaleString() : '—'}
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-sm">
                        {new Date(entry.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end space-x-2">
                          {entry.status === 'pending' && (
                            <button
                              onClick={() => handleScheduleClick(entry)}
                              className="btn-ghost text-blue-600 hover:bg-blue-50"
                              title="Schedule Call"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                              </svg>
                            </button>
                          )}
                          <button
                            onClick={() => handleDelete(entry)}
                            disabled={entry.status !== 'pending' && entry.status !== 'failed'}
                            className="btn-ghost text-red-600 hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed"
                            title="Delete"
                          >
                            <TrashIcon className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      {/* Import Modal */}
      {showImportModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => setShowImportModal(false)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-md mx-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Import CSV</h3>
            <p className="text-gray-600 mb-4">Upload a CSV file with columns: <code className="bg-gray-100 px-1 py-0.5 rounded">contact_name,phone_number</code> (extra columns saved as payload)</p>

            <div className="space-y-4">
              <div>
                <label className="label">Source</label>
                <select value={importSource} onChange={(e) => setImportSource(e.target.value)} className="input">
                  <option value="csv_upload">CSV Upload</option>
                  <option value="api">API Import</option>
                  <option value="manual">Manual Entry</option>
                </select>
              </div>

              <div>
                <label className="label">CSV File</label>
                <input
                  type="file"
                  accept=".csv"
                  onChange={handleFileChange}
                  className="input"
                  required
                />
                {importFile && <p className="text-sm text-gray-500 mt-1">Selected: {importFile.name}</p>}
              </div>

              <div className="flex justify-end space-x-3 pt-4">
                <button onClick={() => setShowImportModal(false)} className="btn-secondary">
                  Cancel
                </button>
                <button onClick={handleImport} disabled={importing || !importFile} className="btn-primary">
                  {importing ? 'Importing...' : 'Import'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Schedule Call Modal */}
      {showScheduleModal && scheduleEntry && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => { setShowScheduleModal(false); setScheduleEntry(null); }}>
          <div className="bg-white rounded-xl p-6 w-full max-w-md mx-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Schedule Call</h3>
            <p className="text-gray-600 mb-4">Schedule a call for <strong>{scheduleEntry.contact_name}</strong> ({scheduleEntry.phone_number})</p>

            <div className="space-y-4">
              <div>
                <label className="label">Date</label>
                <input
                  type="date"
                  value={scheduleDate}
                  onChange={(e) => setScheduleDate(e.target.value)}
                  className="input"
                  min={new Date().toISOString().split('T')[0]}
                  required
                />
              </div>
              <div>
                <label className="label">Time</label>
                <input
                  type="time"
                  value={scheduleTime}
                  onChange={(e) => setScheduleTime(e.target.value)}
                  className="input"
                  required
                />
              </div>

              <div className="flex justify-end space-x-3 pt-4">
                <button onClick={() => { setShowScheduleModal(false); setScheduleEntry(null); }} className="btn-secondary">
                  Cancel
                </button>
                <button onClick={handleScheduleSave} disabled={!scheduleDate || !scheduleTime} className="btn-primary">
                  Schedule
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Import Modal */}
      {showImportModal && (
}

function StatCard({ label, value, icon, color }: { label: string; value: number; icon: React.ReactNode; color: string }) {
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