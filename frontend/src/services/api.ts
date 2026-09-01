import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import type { AxiosInstance } from 'axios';
import { useAuthStore } from '../store/authStore';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

class ApiService {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
      withCredentials: true,
    });

    // Request interceptor to add auth token
    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        const token = useAuthStore.getState().accessToken;
        if (token && config.headers) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for token refresh
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          try {
            await this.refreshToken();
            const token = useAuthStore.getState().accessToken;
            if (token && originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${token}`;
            }
            return this.client(originalRequest);
          } catch (refreshError) {
            useAuthStore.getState().logout();
            window.location.href = '/login';
            return Promise.reject(refreshError);
          }
        }

        return Promise.reject(error);
      }
    );
  }

  async refreshToken(): Promise<void> {
    const refreshToken = useAuthStore.getState().refreshToken;
    if (!refreshToken) throw new Error('No refresh token');

    const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
      refresh_token: refreshToken,
    });

    const { access_token, refresh_token: newRefreshToken } = response.data;
    useAuthStore.getState().setTokens(access_token, newRefreshToken);
  }

  // Auth endpoints
  async register(email: string, password: string) {
    const response = await this.client.post('/auth/register', { email, password });
    return response.data;
  }

  async login(email: string, password: string) {
    const response = await this.client.post('/auth/login', { email, password });
    return response.data;
  }

  async logout() {
    await this.client.post('/auth/logout');
  }

  async getMe() {
    const response = await this.client.get('/auth/me');
    return response.data;
  }

  // Agent endpoints
  async listAgents(params?: { status?: string; direction?: string; limit?: number; offset?: number }) {
    const response = await this.client.get('/agents', { params });
    return response.data;
  }

  async getAgent(agentId: string) {
    const response = await this.client.get(`/agents/${agentId}`);
    return response.data;
  }

  async createAgent(data: any) {
    const response = await this.client.post('/agents', data);
    return response.data;
  }

  async updateAgent(agentId: string, data: any) {
    const response = await this.client.patch(`/agents/${agentId}`, data);
    return response.data;
  }

  async deleteAgent(agentId: string) {
    await this.client.delete(`/agents/${agentId}`);
  }

  async getAgentCompleteness(agentId: string) {
    const response = await this.client.get(`/agents/${agentId}/completeness`);
    return response.data;
  }

  async getPromptVersions(agentId: string, fieldName?: string) {
    const response = await this.client.get(`/agents/${agentId}/prompt-versions`, {
      params: { field_name: fieldName },
    });
    return response.data;
  }

  async rewritePrompt(agentId: string, fieldName: string, currentText: string, instruction?: string) {
    const response = await this.client.post(`/agents/${agentId}/rewrite-prompt`, null, {
      params: { field_name: fieldName, current_text: currentText, instruction },
    });
    return response.data;
  }

  // API Key endpoints
  async getApiKey(agentId: string) {
    const response = await this.client.get(`/agents/${agentId}/api-key`);
    return response.data;
  }

  async regenerateApiKey(agentId: string) {
    const response = await this.client.post(`/agents/${agentId}/api-key/regenerate`);
    return response.data;
  }

  async revokeApiKey(agentId: string) {
    await this.client.delete(`/agents/${agentId}/api-key`);
  }

  async updateWebhookUrl(agentId: string, webhookUrl: string) {
    const response = await this.client.patch(`/agents/${agentId}/api-key/webhook`, { webhook_url: webhookUrl });
    return response.data;
  }

  async getWebSocketUrls(agentId: string) {
    const response = await this.client.get(`/agents/${agentId}/websocket-urls`);
    return response.data;
  }

  async getWebSocketTestToken(agentId: string) {
    const response = await this.client.get(`/agents/${agentId}/websocket-test-token`);
    return response.data;
  }

  // Demo call endpoints (mounted under /demo in main API)
  async startDemoCall(data: any) {
    const response = await this.client.post('/demo/start-call', data);
    return response.data;
  }

  async endDemoCall(sessionId: string) {
    const response = await this.client.post(`/demo/end-call/${sessionId}`);
    return response.data;
  }

  async listDemoSessions() {
    const response = await this.client.get('/demo/sessions');
    return response.data;
  }

  // Health check
  async healthCheck() {
    const response = await this.client.get('/health');
    return response.data;
  }

  // Billing/Account endpoints
  async getUsageStats() {
    const response = await this.client.get('/billing/usage');
    return response.data;
  }

  async createPortalSession() {
    const response = await this.client.post('/billing/portal-session');
    return response.data;
  }

  async createCheckoutSession(plan: string) {
    const response = await this.client.post('/billing/checkout-session', { plan });
    return response.data;
  }

  async createPaymentIntent(plan: string) {
    const response = await this.client.post('/billing/payment-intent', { plan });
    return response.data;
  }

  async getPrices() {
    const response = await this.client.get('/billing/prices');
    return response.data;
  }

  // Admin endpoints
  async getAdminStats() {
    const response = await this.client.get('/admin/stats');
    return response.data;
  }

  async getAdminUsers(params?: { search?: string; page?: number; page_size?: number }) {
    const response = await this.client.get('/admin/users', { params });
    return response.data;
  }

  async getAdminUser(userId: string) {
    const response = await this.client.get(`/admin/users/${userId}`);
    return response.data;
  }

  async suspendUser(userId: string) {
    const response = await this.client.post(`/admin/users/${userId}/suspend`);
    return response.data;
  }

  async unsuspendUser(userId: string) {
    const response = await this.client.post(`/admin/users/${userId}/unsuspend`);
    return response.data;
  }

  async getAdminAgents(params?: { status_filter?: string; page?: number; page_size?: number }) {
    const response = await this.client.get('/admin/agents', { params });
    return response.data;
  }

  async getAdminAuditLogs(params?: { action?: string; user_id?: string; page?: number; page_size?: number }) {
    const response = await this.client.get('/admin/audit-logs', { params });
    return response.data;
  }

  // Cold Call Queue endpoints
  async importQueue(agentId: string, file: File, source?: string) {
    const formData = new FormData();
    formData.append('file', file);
    if (source) formData.append('source', source);
    const response = await this.client.post(`/agents/${agentId}/cold-call-queue/import`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  }

  async importQueueJson(agentId: string, entries: any[], source?: string) {
    const response = await this.client.post(`/agents/${agentId}/cold-call-queue/import`, entries, {
      params: { source: source || 'api' },
    });
    return response.data;
  }

  async listQueueEntries(agentId: string, params?: { status?: string; limit?: number; offset?: number; sort_by?: string; sort_order?: string }) {
    const response = await this.client.get(`/agents/${agentId}/cold-call-queue`, { params });
    return response.data;
  }

  async getQueueStats(agentId: string) {
    const response = await this.client.get(`/agents/${agentId}/cold-call-queue/stats`);
    return response.data;
  }

  async updateQueueEntry(agentId: string, entryId: string, data: any) {
    const response = await this.client.patch(`/agents/${agentId}/cold-call-queue/${entryId}`, data);
    return response.data;
  }

  async retryFailedQueueEntries(agentId: string, maxRetries?: number) {
    const response = await this.client.post(`/agents/${agentId}/cold-call-queue/retry-failed`, null, {
      params: { max_retries: maxRetries || 3 },
    });
    return response.data;
  }

  async deleteQueueEntry(agentId: string, entryId: string) {
    await this.client.delete(`/agents/${agentId}/cold-call-queue/${entryId}`);
  }
// Generic request methods
  async get(url: string, config?: any) {
    const response = await this.client.get(url, config);
    return response.data;
  }

  async post(url: string, data?: any, config?: any) {
    const response = await this.client.post(url, data, config);
    return response.data;
  }

  async patch(url: string, data: any, config?: any) {
    const response = await this.client.patch(url, data, config);
    return response.data;
  }

  async delete(url: string, config?: any) {
    const response = await this.client.delete(url, config);
    return response.data;
  }
}

export const api = new ApiService();