const BASE = '';

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...init?.headers },
  });
  if (res.status === 401) {
    localStorage.removeItem('token');
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export async function login(username: string, password: string) {
  const data = await request<{ access_token: string }>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
  localStorage.setItem('token', data.access_token);
  return data;
}

export function logout() {
  localStorage.removeItem('token');
}

export function getMe() {
  return request<{ username: string }>('/auth/me');
}

export interface EventItem {
  id: string;
  occurred_at: string;
  product: string;
  deployment: string;
  pipeline: string;
  actor_id?: string;
  actor_raw: string;
  operation: string;
  category: string;
  severity: string;
  object_type: string;
  object_ref: { id: string; name: string; container?: string };
  source_ip?: string;
  context?: Record<string, unknown>;
  raw?: Record<string, unknown>;
}

export interface EventsResponse {
  items: EventItem[];
  total: number;
  skip: number;
  limit: number;
}

export function getEvents(params: Record<string, string | string[]>) {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (Array.isArray(v)) v.forEach(x => sp.append(k, x));
    else if (v) sp.append(k, v);
  }
  return request<EventsResponse>(`/events?${sp}`);
}

export function getEvent(id: string) {
  return request<EventItem>(`/events/${id}`);
}

export interface TimeseriesBucket {
  bucket: string;
  group: string;
  count: number;
}

export function getTimeseries(params: Record<string, string | string[]>) {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (Array.isArray(v)) v.forEach(x => sp.append(k, x));
    else if (v) sp.append(k, v);
  }
  return request<TimeseriesBucket[]>(`/aggregations/timeseries?${sp}`);
}

export interface TopItem {
  key: string;
  count: number;
}

export function getTop(params: Record<string, string | string[]>) {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (Array.isArray(v)) v.forEach(x => sp.append(k, x));
    else if (v) sp.append(k, v);
  }
  return request<TopItem[]>(`/aggregations/top?${sp}`);
}

export interface Summary {
  total_events: number;
  by_product: Record<string, number>;
  by_category: Record<string, number>;
  by_severity: Record<string, number>;
  unique_actors: number;
}

export function getSummary(params: Record<string, string | string[]>) {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (Array.isArray(v)) v.forEach(x => sp.append(k, x));
    else if (v) sp.append(k, v);
  }
  return request<Summary>(`/aggregations/summary?${sp}`);
}

export interface WorkItem {
  object_id: string;
  product: string;
  name: string;
  container?: string;
  object_type: string;
  updated_at: string;
  role: string;
}

export interface ItemsResponse {
  items: WorkItem[];
  total: number;
  skip: number;
  limit: number;
}

export function getItems(params: Record<string, string | string[]>) {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (Array.isArray(v)) v.forEach(x => sp.append(k, x));
    else if (v) sp.append(k, v);
  }
  return request<ItemsResponse>(`/items?${sp}`);
}

export interface ConnectorStatus {
  connector: string;
  product: string;
  deployment: string;
  cursor: string | null;
  last_success_at: string | null;
  last_error: string | null;
  note?: string;
}

export function getSyncStatus() {
  return request<ConnectorStatus[]>('/sync-status');
}

export function exportData(params: Record<string, string | string[]>, format: 'csv' | 'pdf' = 'csv') {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (Array.isArray(v)) v.forEach(x => sp.append(k, x));
    else if (v) sp.append(k, v);
  }
  sp.set('format', format);
  return fetch(`${BASE}/exports?${sp}`, {
    method: 'POST',
    headers: authHeaders(),
  });
}

export function exportCsv(params: Record<string, string | string[]>) {
  return exportData(params, 'csv');
}

export interface ScheduledReport {
  id: string;
  name: string;
  schedule: string;
  format: string;
  filters: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
  created_by: string;
  last_run_at: string | null;
  last_output: string | null;
  last_count: number | null;
}

export function getScheduledReports() {
  return request<ScheduledReport[]>('/reports/scheduled');
}

export function createScheduledReport(body: {
  name: string;
  schedule: string;
  format: string;
  filters: Record<string, unknown>;
}) {
  return request<ScheduledReport>('/reports/scheduled', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function deleteScheduledReport(id: string) {
  return request<{ status: string }>(`/reports/scheduled/${id}`, {
    method: 'DELETE',
  });
}
