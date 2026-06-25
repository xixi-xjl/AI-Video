<template>
  <section id="comparison" class="py-16 sm:py-20 bg-bg-section" aria-labelledby="comparison-heading">
    <div class="max-w-5xl mx-auto px-4 sm:px-6">
      <div class="text-center mb-12">
        <h2 id="comparison-heading" class="text-2xl sm:text-3xl font-bold text-text-primary mb-3">
          {{ APP_NAME }} 与其他视频下载工具对比
        </h2>
        <p class="text-text-secondary text-base max-w-xl mx-auto">
          一张表看清 {{ APP_NAME }} 的核心优势，更新于 2026 年 3 月
        </p>
      </div>

      <div class="overflow-x-auto rounded-2xl border border-border-light shadow-sm">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-white/5 text-text-primary">
              <th class="text-left px-5 py-3.5 font-semibold">功能对比</th>
              <th class="px-5 py-3.5 font-semibold text-primary max-w-[8rem]">{{ APP_NAME }}</th>
              <th class="px-5 py-3.5 font-semibold">其他在线工具</th>
              <th class="px-5 py-3.5 font-semibold">桌面下载软件</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            <tr v-for="(row, i) in rows" :key="row.feature" :class="i % 2 === 1 ? 'bg-white/[0.02]' : ''">
              <td class="px-5 py-3 text-text-primary font-medium">{{ row.feature }}</td>
              <td class="px-5 py-3 text-center">
                <span v-if="row.platform === true" class="text-success text-base">✓</span>
                <span v-else-if="row.platform === false" class="text-text-muted">✗</span>
                <span v-else class="text-text-primary">{{ row.platform }}</span>
              </td>
              <td class="px-5 py-3 text-center text-text-secondary">
                <span v-if="row.online === true" class="text-success text-base">✓</span>
                <span v-else-if="row.online === false" class="text-text-muted">✗</span>
                <span v-else>{{ row.online }}</span>
              </td>
              <td class="px-5 py-3 text-center text-text-secondary">
                <span v-if="row.desktop === true" class="text-success text-base">✓</span>
                <span v-else-if="row.desktop === false" class="text-text-muted">✗</span>
                <span v-else>{{ row.desktop }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<script setup>
import { APP_NAME } from '../constants/brand.js'

const rows = [
  { feature: '支持平台数量', platform: '1800+', online: '10-50', desktop: '100-500' },
  { feature: 'AI 视频总结', platform: true, online: false, desktop: false },
  { feature: '思维导图生成', platform: true, online: false, desktop: false },
  { feature: '字幕下载', platform: 'SRT/VTT/TXT', online: '部分支持', desktop: '部分支持' },
  { feature: '抖音无水印下载', platform: true, online: '部分支持', desktop: '需登录' },
  { feature: '最高画质', platform: '4K', online: '720p-1080p', desktop: '4K' },
  { feature: '无需安装', platform: true, online: true, desktop: false },
  { feature: '手机浏览器可用', platform: true, online: '部分支持', desktop: false },
  { feature: '费用', platform: '免费', online: '免费/付费', desktop: '付费为主' },
]
</script>
