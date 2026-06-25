<template>
  <div class="min-h-screen bg-slate-100">
    <!-- 登录页 -->
    <div v-if="!admin" class="min-h-screen flex items-center justify-center p-4">
      <div class="w-full max-w-md bg-white rounded-2xl shadow-lg p-8">
        <h1 class="text-2xl font-bold text-slate-800 mb-1">AI多平台视频下载分析平台 · 管理后台</h1>
        <p class="text-sm text-slate-500 mb-6">请使用管理员账号登录</p>
        <form @submit.prevent="handleLogin" class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">邮箱</label>
            <input v-model="loginForm.email" type="email" required
              class="w-full h-11 px-4 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/30" />
          </div>
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">密码</label>
            <input v-model="loginForm.password" type="password" required
              class="w-full h-11 px-4 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/30" />
          </div>
          <p v-if="loginError" class="text-sm text-red-600">{{ loginError }}</p>
          <button type="submit" :disabled="loginLoading"
            class="w-full h-11 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-medium cursor-pointer disabled:opacity-50">
            {{ loginLoading ? '登录中...' : '登录' }}
          </button>
        </form>
      </div>
    </div>

    <!-- 管理面板 -->
    <div v-else>
      <header class="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div class="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
          <div class="flex items-center gap-3">
            <span class="font-semibold text-slate-800">AI多平台视频下载分析平台 · 管理后台</span>
            <span class="text-xs text-slate-400">{{ admin.email }}</span>
          </div>
          <div class="flex items-center gap-3">
            <a href="/" class="text-sm text-blue-600 hover:underline">返回前台</a>
            <button @click="handleLogout" class="text-sm text-slate-500 hover:text-slate-800 cursor-pointer">退出</button>
          </div>
        </div>
        <nav class="max-w-7xl mx-auto px-4 flex gap-1 border-t border-slate-100">
          <button v-for="tab in tabs" :key="tab.key" @click="activeTab = tab.key"
            :class="['px-4 py-2.5 text-sm font-medium border-b-2 transition-colors cursor-pointer',
              activeTab === tab.key ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-800']">
            {{ tab.label }}
          </button>
        </nav>
      </header>

      <main class="max-w-7xl mx-auto px-4 py-6">
        <!-- 仪表盘 -->
        <div v-if="activeTab === 'dashboard'">
          <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <div v-for="card in statCards" :key="card.label" class="bg-white rounded-xl p-5 border border-slate-200">
              <div class="text-2xl font-bold text-slate-800">{{ card.value }}</div>
              <div class="text-sm text-slate-500 mt-1">{{ card.label }}</div>
            </div>
          </div>
        </div>

        <!-- 用户管理 -->
        <div v-if="activeTab === 'users'" class="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div class="p-4 border-b border-slate-100 flex gap-3">
            <input v-model="userSearch" @keydown.enter="loadUsers(1)" placeholder="搜索邮箱..."
              class="flex-1 h-10 px-4 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30" />
            <button @click="loadUsers(1)" class="px-4 h-10 rounded-lg bg-blue-600 text-white text-sm cursor-pointer">搜索</button>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="bg-slate-50 text-slate-600">
                <tr>
                  <th class="px-4 py-3 text-left">ID</th>
                  <th class="px-4 py-3 text-left">邮箱</th>
                  <th class="px-4 py-3 text-left">VIP</th>
                  <th class="px-4 py-3 text-left">今日用量</th>
                  <th class="px-4 py-3 text-left">注册时间</th>
                  <th class="px-4 py-3 text-left">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="u in users.items" :key="u.id" class="border-t border-slate-100 hover:bg-slate-50">
                  <td class="px-4 py-3">{{ u.id }}</td>
                  <td class="px-4 py-3">
                    {{ u.email }}
                    <span v-if="u.is_admin" class="ml-1 text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded">管理员</span>
                  </td>
                  <td class="px-4 py-3">
                    <span :class="u.is_vip ? 'text-green-600' : 'text-slate-400'">{{ u.is_vip ? '是' : '否' }}</span>
                  </td>
                  <td class="px-4 py-3">{{ u.daily_summary_count || 0 }}</td>
                  <td class="px-4 py-3 text-slate-500">{{ formatDate(u.created_at) }}</td>
                  <td class="px-4 py-3 space-x-2 whitespace-nowrap">
                    <button @click="grantVip(u.id)" class="text-xs text-blue-600 hover:underline cursor-pointer">赠VIP 30天</button>
                    <button @click="resetQuota(u.id)" class="text-xs text-orange-600 hover:underline cursor-pointer">重置配额</button>
                    <button v-if="u.is_vip" @click="toggleVipOff(u.id)" class="text-xs text-slate-500 hover:underline cursor-pointer">取消VIP</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="p-4 flex justify-between items-center border-t border-slate-100 text-sm text-slate-500">
            <span>共 {{ users.total }} 条</span>
            <div class="flex gap-2">
              <button :disabled="users.page <= 1" @click="loadUsers(users.page - 1)"
                class="px-3 py-1 rounded border cursor-pointer disabled:opacity-40">上一页</button>
              <span>第 {{ users.page }} 页</span>
              <button :disabled="users.page * users.limit >= users.total" @click="loadUsers(users.page + 1)"
                class="px-3 py-1 rounded border cursor-pointer disabled:opacity-40">下一页</button>
            </div>
          </div>
        </div>

        <!-- 订单管理 -->
        <div v-if="activeTab === 'orders'" class="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="bg-slate-50 text-slate-600">
                <tr>
                  <th class="px-4 py-3 text-left">订单号</th>
                  <th class="px-4 py-3 text-left">用户</th>
                  <th class="px-4 py-3 text-left">金额</th>
                  <th class="px-4 py-3 text-left">状态</th>
                  <th class="px-4 py-3 text-left">时间</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="o in orders.items" :key="o.id" class="border-t border-slate-100">
                  <td class="px-4 py-3 font-mono text-xs">{{ o.order_no }}</td>
                  <td class="px-4 py-3">{{ o.user_email }}</td>
                  <td class="px-4 py-3">¥{{ (o.amount / 100).toFixed(2) }}</td>
                  <td class="px-4 py-3">
                    <span :class="o.status === 'paid' ? 'text-green-600' : 'text-orange-500'">{{ o.status }}</span>
                  </td>
                  <td class="px-4 py-3 text-slate-500">{{ formatDate(o.created_at) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- AI 总结记录 -->
        <div v-if="activeTab === 'summaries'" class="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="bg-slate-50 text-slate-600">
                <tr>
                  <th class="px-4 py-3 text-left">ID</th>
                  <th class="px-4 py-3 text-left">用户</th>
                  <th class="px-4 py-3 text-left">视频标题</th>
                  <th class="px-4 py-3 text-left">摘要长度</th>
                  <th class="px-4 py-3 text-left">更新时间</th>
                  <th class="px-4 py-3 text-left">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="s in summaries.items" :key="s.id" class="border-t border-slate-100">
                  <td class="px-4 py-3">{{ s.id }}</td>
                  <td class="px-4 py-3">{{ s.user_email }}</td>
                  <td class="px-4 py-3 max-w-xs truncate" :title="s.video_title">{{ s.video_title || '—' }}</td>
                  <td class="px-4 py-3">{{ s.summary_length || 0 }} 字</td>
                  <td class="px-4 py-3 text-slate-500">{{ formatDate(s.updated_at) }}</td>
                  <td class="px-4 py-3">
                    <button @click="handleDeleteSummary(s.id)" class="text-xs text-red-600 hover:underline cursor-pointer">删除</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 系统状态 -->
        <div v-if="activeTab === 'system'" class="bg-white rounded-xl border border-slate-200 p-6">
          <div v-if="system" class="space-y-4 text-sm">
            <div class="flex justify-between py-2 border-b border-slate-100">
              <span class="text-slate-600">DeepSeek API</span>
              <span :class="system.deepseek_configured ? 'text-green-600' : 'text-red-500'">
                {{ system.deepseek_configured ? '已配置' : '未配置' }}
              </span>
            </div>
            <div class="flex justify-between py-2 border-b border-slate-100">
              <span class="text-slate-600">Stripe 支付</span>
              <span :class="system.stripe_configured ? 'text-green-600' : 'text-slate-400'">
                {{ system.stripe_configured ? '已配置' : '未配置' }}
              </span>
            </div>
            <div class="flex justify-between py-2 border-b border-slate-100">
              <span class="text-slate-600">Whisper 语音识别</span>
              <span :class="system.whisper.enabled ? 'text-green-600' : 'text-red-500'">
                {{ system.whisper.enabled ? '已启用' : '已禁用' }}
              </span>
            </div>
            <div class="flex justify-between py-2 border-b border-slate-100">
              <span class="text-slate-600">Whisper 模型</span>
              <span class="text-slate-800">{{ system.whisper.model }} ({{ system.whisper.device }})</span>
            </div>
            <div class="flex justify-between py-2">
              <span class="text-slate-600">最大识别时长</span>
              <span class="text-slate-800">{{ Math.round(system.whisper.max_seconds / 60) }} 分钟</span>
            </div>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import {
  adminLogin, clearAdminToken, verifyAdminSession,
  fetchStats, fetchUsers, updateUser, fetchOrders, fetchSummaries, deleteSummary, fetchSystem,
} from './api.js'

const admin = ref(null)
const activeTab = ref('dashboard')
const loginForm = ref({ email: '', password: '' })
const loginError = ref('')
const loginLoading = ref(false)

const stats = ref(null)
const users = ref({ items: [], total: 0, page: 1, limit: 20 })
const orders = ref({ items: [], total: 0, page: 1, limit: 20 })
const summaries = ref({ items: [], total: 0, page: 1, limit: 20 })
const system = ref(null)
const userSearch = ref('')

const tabs = [
  { key: 'dashboard', label: '仪表盘' },
  { key: 'users', label: '用户管理' },
  { key: 'orders', label: '订单管理' },
  { key: 'summaries', label: 'AI 总结' },
  { key: 'system', label: '系统状态' },
]

const statCards = computed(() => {
  if (!stats.value) return []
  const s = stats.value
  return [
    { label: '注册用户', value: s.total_users },
    { label: 'VIP 用户', value: s.vip_users },
    { label: '已支付订单', value: s.paid_orders },
    { label: 'AI 总结总数', value: s.total_summaries },
    { label: '今日新增总结', value: s.today_summaries },
    { label: '累计收入', value: '¥' + (s.revenue_cents / 100).toFixed(2) },
  ]
})

function formatDate(str) {
  if (!str) return '—'
  return str.replace('T', ' ').slice(0, 16)
}

async function handleLogin() {
  loginLoading.value = true
  loginError.value = ''
  try {
    admin.value = await adminLogin(loginForm.value.email, loginForm.value.password)
    await loadDashboard()
  } catch (e) {
    loginError.value = e.response?.data?.detail || e.message || '登录失败'
  } finally {
    loginLoading.value = false
  }
}

function handleLogout() {
  clearAdminToken()
  admin.value = null
}

async function loadDashboard() {
  stats.value = await fetchStats()
}

async function loadUsers(page = 1) {
  users.value = await fetchUsers(page, userSearch.value)
}

async function loadOrders(page = 1) {
  orders.value = await fetchOrders(page)
}

async function loadSummaries(page = 1) {
  summaries.value = await fetchSummaries(page)
}

async function loadSystem() {
  system.value = await fetchSystem()
}

async function grantVip(userId) {
  await updateUser(userId, { vip_days: 30 })
  await loadUsers(users.value.page)
}

async function resetQuota(userId) {
  await updateUser(userId, { reset_quota: true })
  await loadUsers(users.value.page)
}

async function toggleVipOff(userId) {
  await updateUser(userId, { is_vip: 0 })
  await loadUsers(users.value.page)
}

async function handleDeleteSummary(id) {
  if (!confirm('确认删除该总结记录？')) return
  await deleteSummary(id)
  await loadSummaries(summaries.value.page)
}

watch(activeTab, async (tab) => {
  if (!admin.value) return
  if (tab === 'dashboard') await loadDashboard()
  if (tab === 'users') await loadUsers()
  if (tab === 'orders') await loadOrders()
  if (tab === 'summaries') await loadSummaries()
  if (tab === 'system') await loadSystem()
})

onMounted(async () => {
  admin.value = await verifyAdminSession()
  if (admin.value) await loadDashboard()
})
</script>
