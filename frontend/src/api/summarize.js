/**
 * AI 视频总结 API 封装
 * 使用原生 fetch + ReadableStream 处理 SSE 流式响应
 */

import { getToken } from './auth'

async function handleSSEStream(response, callbacks) {
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let currentEvent = ''
  let dataLines = []
  let hasData = false

  function dispatch() {
    if (hasData && currentEvent) {
      const handler = callbacks[currentEvent]
      if (handler) handler(dataLines.join('\n'))
    }
    dataLines = []
    hasData = false
    currentEvent = ''
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line === '') {
        dispatch()
        continue
      }

      if (line.startsWith(':')) continue

      const colonIdx = line.indexOf(':')
      if (colonIdx < 0) continue

      const field = line.slice(0, colonIdx)
      let val = line.slice(colonIdx + 1)
      if (val.startsWith(' ')) val = val.slice(1)

      if (field === 'event') {
        currentEvent = val
      } else if (field === 'data') {
        hasData = true
        dataLines.push(val)
      }
    }
  }
  dispatch()
}

function authHeaders() {
  const token = getToken()
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return headers
}

export async function summarizeVideo(url, language = 'zh', callbacks = {}, videoTitle = '') {
  const response = await fetch('/api/summarize', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ url, language, video_title: videoTitle }),
  })

  if (!response.ok) {
    throw new Error(`请求失败: ${response.status}`)
  }

  await handleSSEStream(response, callbacks)
}

export async function chatWithVideo(url, question, subtitleText = '', callbacks = {}, videoTitle = '') {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({
      url,
      question,
      subtitle_text: subtitleText,
      video_title: videoTitle,
    }),
  })

  if (!response.ok) {
    if (response.status === 401) throw new Error('NEED_LOGIN')
    throw new Error(`请求失败: ${response.status}`)
  }

  await handleSSEStream(response, callbacks)
}

export async function generateContent({ url, scenario, subtitleText, videoTitle = '', language = 'zh' }, callbacks = {}) {
  const response = await fetch('/api/generate-content', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({
      url,
      scenario,
      subtitle_text: subtitleText,
      video_title: videoTitle,
      language,
    }),
  })

  if (!response.ok) {
    if (response.status === 401) throw new Error('NEED_LOGIN')
    throw new Error(`请求失败: ${response.status}`)
  }

  await handleSSEStream(response, callbacks)
}

export async function fetchSubtitles(url, language = 'zh') {
  const response = await fetch('/api/subtitles', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ url, language }),
  })
  if (!response.ok) {
    if (response.status === 401) throw new Error('NEED_LOGIN')
    let detail = '字幕获取失败'
    try {
      const err = await response.json()
      detail = err.detail || detail
    } catch {}
    throw new Error(detail)
  }
  const res = await response.json()
  return res.data
}

export async function getCachedSummary(url) {
  const token = getToken()
  if (!token) return null
  const response = await fetch(`/api/summaries/cached?url=${encodeURIComponent(url)}`, {
    headers: authHeaders(),
  })
  if (!response.ok) return null
  const res = await response.json()
  return res.data
}
