import axios from 'axios'

const TOKEN_KEY = 'platform_admin_token'

const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export function getAdminToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setAdminToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearAdminToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export async function adminLogin(email, password) {
  const res = await api.post('/auth/login', { email, password })
  const token = res.data.data.token
  setAdminToken(token)
  const me = await api.get('/admin/me')
  if (!me.data.data.is_admin) {
    clearAdminToken()
    throw new Error('该账号不是管理员')
  }
  return me.data.data
}

export async function fetchStats() {
  const res = await api.get('/admin/stats')
  return res.data.data
}

export async function fetchUsers(page = 1, q = '') {
  const res = await api.get('/admin/users', { params: { page, limit: 20, q } })
  return res.data.data
}

export async function updateUser(userId, payload) {
  const res = await api.patch(`/admin/users/${userId}`, payload)
  return res.data.data
}

export async function fetchOrders(page = 1) {
  const res = await api.get('/admin/orders', { params: { page, limit: 20 } })
  return res.data.data
}

export async function fetchSummaries(page = 1) {
  const res = await api.get('/admin/summaries', { params: { page, limit: 20 } })
  return res.data.data
}

export async function deleteSummary(id) {
  await api.delete(`/admin/summaries/${id}`)
}

export async function fetchSystem() {
  const res = await api.get('/admin/system')
  return res.data.data
}

export async function verifyAdminSession() {
  if (!getAdminToken()) return null
  const res = await api.get('/admin/me')
  if (!res.data.data.is_admin) {
    clearAdminToken()
    return null
  }
  return res.data.data
}
