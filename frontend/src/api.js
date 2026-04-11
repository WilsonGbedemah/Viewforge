const BASE = '/api'

function getToken() {
  return localStorage.getItem('vf_token')
}

async function req(method, path, body) {
  const token = getToken()
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  // Auth
  signup: (d) => req('POST', '/auth/signup', d),
  login:  (d) => req('POST', '/auth/login',  d),
  logout: ()  => req('POST', '/auth/logout'),
  me:     ()  => req('GET',  '/auth/me'),

  // Stats
  stats: () => req('GET', '/stats/'),

  // Accounts
  listAccounts: () => req('GET', '/accounts/'),
  createAccount: (d) => req('POST', '/accounts/', d),
  updateAccount: (id, d) => req('PATCH', `/accounts/${id}`, d),
  deleteAccount: (id) => req('DELETE', `/accounts/${id}`),
  resetAccountDaily: (id) => req('POST', `/accounts/${id}/reset-daily`),
  autoCreateAccount: (d) => req('POST', '/accounts/auto-create', d),
  getCreationStatus: (id) => req('GET', `/accounts/auto-create-status/${id}`),
  submitCreationInput: (id, value) => req('POST', `/accounts/auto-create-input/${id}`, { value }),

  // Proxies
  listProxies: () => req('GET', '/proxies/'),
  createProxy: (d) => req('POST', '/proxies/', d),
  updateProxy: (id, d) => req('PATCH', `/proxies/${id}`, d),
  deleteProxy: (id) => req('DELETE', `/proxies/${id}`),

  // Campaigns
  listCampaigns: () => req('GET', '/campaigns/'),
  createCampaign: (d) => req('POST', '/campaigns/', d),
  updateCampaign: (id, d) => req('PATCH', `/campaigns/${id}`, d),
  deleteCampaign: (id) => req('DELETE', `/campaigns/${id}`),
  startCampaign: (id) => req('POST', `/campaigns/${id}/start`),
  stopCampaign: (id) => req('POST', `/campaigns/${id}/stop`),
  campaignSessions: (id) => req('GET', `/campaigns/${id}/sessions`),

  // Stats
  exportSessions: (campaign_id) => {
    const q = campaign_id ? `?campaign_id=${campaign_id}` : ''
    window.open(`${BASE}/stats/export${q}`, '_blank')
  },

  // Logs
  listLogs: (params = {}) => {
    const q = new URLSearchParams()
    if (params.limit) q.set('limit', params.limit)
    if (params.campaign_id) q.set('campaign_id', params.campaign_id)
    if (params.account_id) q.set('account_id', params.account_id)
    if (params.level) q.set('level', params.level)
    return req('GET', `/logs/?${q}`)
  },
  exportLogs: (campaign_id) => {
    const q = campaign_id ? `?campaign_id=${campaign_id}` : ''
    window.open(`${BASE}/logs/export${q}`, '_blank')
  },
  clearLogs: (campaign_id) => {
    const q = campaign_id ? `?campaign_id=${campaign_id}` : ''
    return req('DELETE', `/logs/${q}`)
  },
}

// WebSocket live log stream
export function connectLogStream(onMessage) {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${proto}://${window.location.host}/ws/logs`)
  ws.onmessage = (e) => {
    try { onMessage(JSON.parse(e.data)) } catch (_) {}
  }
  ws.onerror = () => {}
  ws.onclose = () => {}
  return ws
}
