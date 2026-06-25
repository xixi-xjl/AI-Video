<template>
  <section class="relative overflow-hidden bg-bg-main transition-all"
    :class="compact ? 'pt-6 pb-4 sm:pt-8 sm:pb-6' : 'pt-16 pb-12 sm:pt-24 sm:pb-16'"
  >
    <!-- 动态光晕背景 -->
    <div class="absolute inset-0 overflow-hidden pointer-events-none">
      <div class="absolute -top-60 -right-60 w-[500px] h-[500px] bg-purple-600/20 rounded-full blur-[120px]"></div>
      <div class="absolute -bottom-40 -left-40 w-[400px] h-[400px] bg-cyan-500/15 rounded-full blur-[100px]"></div>
      <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-violet-900/10 rounded-full blur-[140px]"></div>
    </div>
    <!-- 网格装饰 -->
    <div class="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.015)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.015)_1px,transparent_1px)] bg-[size:60px_60px] pointer-events-none"></div>

    <div class="relative max-w-4xl mx-auto px-4 sm:px-6 text-center">
      <template v-if="showSlogan">
        <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/5 border border-white/10 text-sm text-text-secondary backdrop-blur-sm"
          :class="compact ? 'mb-3' : 'mb-6'"
        >
          <span class="w-2 h-2 rounded-full bg-success animate-pulse"></span>
          支持 1800+ 平台，永久免费使用
        </div>
        <h1 :class="compact ? 'text-2xl sm:text-3xl mb-2' : 'text-3xl sm:text-5xl mb-4'" class="font-bold leading-tight">
          <span class="gradient-text">AI多平台</span><span class="text-text-primary">视频下载分析平台</span>
        </h1>
        <p :class="compact ? 'mb-4 text-sm sm:text-base' : 'mb-10 text-base sm:text-lg'" class="text-text-secondary max-w-2xl mx-auto leading-relaxed">
          粘贴视频链接，智能解析下载并 AI 总结。支持 YouTube、Bilibili、抖音、TikTok 等 1800+ 平台，多种清晰度可选，一键生成摘要与思维导图
        </p>
      </template>

      <div class="max-w-2xl mx-auto">
        <form @submit.prevent="onSubmit" class="relative flex items-center" role="search" aria-label="视频链接解析">
          <div class="relative flex-1">
            <label for="video-url-input" class="sr-only">粘贴视频链接进行解析下载</label>
            <svg class="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
            <input
              id="video-url-input"
              v-model="url"
              type="url"
              :placeholder="placeholder"
              class="w-full h-13 sm:h-14 pl-12 pr-4 rounded-full sm:rounded-r-none border border-white/10 bg-white/[0.06] backdrop-blur-sm text-base text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary/50 transition-all"
              :disabled="loading"
              autocomplete="url"
            />
          </div>
          <button
            type="submit"
            :disabled="loading || !url.trim()"
            class="hidden sm:flex items-center gap-2 h-14 px-8 rounded-r-full bg-gradient-to-r from-purple-600 to-cyan-500 hover:opacity-90 text-white font-medium text-base transition-all disabled:opacity-50 disabled:cursor-not-allowed glow-btn cursor-pointer"
          >
            <svg v-if="loading" class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            {{ loading ? '解析中...' : '解析视频' }}
          </button>
          <button
            type="submit"
            :disabled="loading || !url.trim()"
            class="sm:hidden absolute right-2 top-1/2 -translate-y-1/2 w-9 h-9 flex items-center justify-center rounded-full bg-gradient-to-r from-purple-600 to-cyan-500 text-white disabled:opacity-50 cursor-pointer"
          >
            <svg v-if="loading" class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </button>
        </form>
        <div v-if="showSlogan" class="flex flex-wrap items-center justify-center gap-3 mt-5 text-xs text-text-muted">
          <span>试试：</span>
          <button
            v-for="example in examples"
            :key="example.label"
            @click="url = example.url"
            class="px-3 py-1 rounded-full bg-white/5 border border-white/10 hover:border-primary/50 hover:text-primary transition-all cursor-pointer"
          >
            {{ example.label }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'

defineProps({ loading: Boolean, compact: Boolean, showSlogan: { type: Boolean, default: true } })
const emit = defineEmits(['parse'])

const url = ref('')
const placeholder = 'https://www.youtube.com/watch?v=... 粘贴视频链接'
const examples = [
  { label: 'YouTube', url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ' },
  { label: 'Bilibili', url: 'https://www.bilibili.com/video/BV1GJ411x7h7' },
  { label: 'Douyin', url: 'https://www.douyin.com/root/search/%E7%AE%97%E6%B3%95%E5%B7%A5%E7%A8%8B%E5%B8%88?aid=f339c57f-46bc-4887-925b-0ff4c0ef85d0&modal_id=7207818159049428228&type=general' },
  { label: 'Twitter/X', url: 'https://x.com/elonmusk/status/1234567890' },
]

function onSubmit() {
  let u = url.value.trim()
  if (!u) return
  if (u.includes('bilibili.com') && !u.includes('www.bilibili.com')) u = u.replace('bilibili.com', 'www.bilibili.com')
  emit('parse', u)
}
</script>
