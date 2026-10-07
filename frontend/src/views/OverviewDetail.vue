<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>片区汇总明细</h2>
        <p class="page-desc">
          {{ detail.date }} · {{ detail.region }} · {{ detail.criteria_note }}
          <span v-if="detail.generated_at">· 汇总生成于 {{ detail.generated_at }}</span>
        </p>
      </div>
      <div class="page-actions">
        <button class="btn ghost" type="button" @click="goBack">返回运营概览</button>
      </div>
    </header>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">当日新增</span>
        <strong class="stat-value">{{ detail.counts.created }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">待处理</span>
        <strong class="stat-value">{{ detail.counts.pending }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">异常量</span>
        <strong class="stat-value">{{ detail.counts.abnormal }}</strong>
      </article>
    </div>

    <h3 class="group-title">告警事件</h3>
    <table class="data-table">
      <thead>
        <tr><th>告警编号</th><th>告警类型</th><th>触发时间</th><th>当前状态</th><th>命中口径</th></tr>
      </thead>
      <tbody>
        <tr v-for="entry in alarmEntries" :key="`alarm-${entry.id}`">
          <td>{{ entry.fields['告警编号'] ?? '—' }}</td>
          <td>{{ entry.fields['告警类型'] ?? '—' }}</td>
          <td>{{ entry.fields['触发时间'] ?? '—' }}</td>
          <td>{{ entry.fields.status ?? '—' }}</td>
          <td>{{ kindLabels(entry.kinds) }}</td>
        </tr>
        <tr v-if="!alarmEntries.length">
          <td colspan="5" class="empty-state">该片区当天没有命中汇总的告警</td>
        </tr>
      </tbody>
    </table>

    <h3 class="group-title">设备缺陷</h3>
    <table class="data-table">
      <thead>
        <tr><th>缺陷编号</th><th>缺陷设备</th><th>发现日期</th><th>整改时限</th><th>当前状态</th><th>命中口径</th></tr>
      </thead>
      <tbody>
        <tr v-for="entry in defectEntries" :key="`defect-${entry.id}`">
          <td>{{ entry.fields['缺陷编号'] ?? '—' }}</td>
          <td>{{ entry.fields['缺陷设备'] ?? '—' }}</td>
          <td>{{ entry.fields['发现日期'] ?? '—' }}</td>
          <td>{{ entry.fields['整改时限'] ?? '—' }}</td>
          <td>{{ entry.fields.status ?? '—' }}</td>
          <td>{{ kindLabels(entry.kinds) }}</td>
        </tr>
        <tr v-if="!defectEntries.length">
          <td colspan="6" class="empty-state">该片区当天没有命中汇总的缺陷</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>明细与概览卡片读同一份落库汇总，两处不会对不上。</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { fetchJson } from '@/api/client'

type DetailEntry = {
  module: string
  id: number
  kinds: string[]
  fields: Record<string, string | number | null>
}

type Detail = {
  date: string
  region: string
  criteria_version: number
  criteria_note: string
  generated_at: string
  counts: { pending: number; abnormal: number; created: number }
  entries: DetailEntry[]
}

const KIND_LABELS: Record<string, string> = {
  pending: '待处理',
  abnormal: '异常量',
  created: '当日新增',
}

const route = useRoute()
const router = useRouter()

const detail = ref<Detail>({
  date: String(route.query.day ?? ''),
  region: String(route.query.region ?? ''),
  criteria_version: 0,
  criteria_note: '',
  generated_at: '',
  counts: { pending: 0, abnormal: 0, created: 0 },
  entries: [],
})
const errorMessage = ref('')

const alarmEntries = computed(() => detail.value.entries.filter((entry) => entry.module === 'alarm'))
const defectEntries = computed(() => detail.value.entries.filter((entry) => entry.module === 'defect'))

function kindLabels(kinds: string[]) {
  return kinds.map((kind) => KIND_LABELS[kind] ?? kind).join('、')
}

function goBack() {
  void router.push({ path: '/', query: { day: detail.value.date } })
}

onMounted(async () => {
  errorMessage.value = ''
  try {
    detail.value = await fetchJson<Detail>(
      `/api/overview/details?day=${detail.value.date}&region=${encodeURIComponent(detail.value.region)}`,
    )
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '汇总明细读取失败'
  }
})
</script>

<style scoped>
.group-title { font-size: 14px; margin: 16px 0 8px; }
</style>
