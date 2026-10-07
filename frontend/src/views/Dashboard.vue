<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">按片区汇总告警与缺陷的待处理量和异常量，卡片、明细与模块统计读同一份落库数据。</p>
      </div>
      <div class="page-actions">
        <input v-model="queryDate" type="date" class="date-input" />
        <button class="btn" type="button" @click="reload">查询</button>
        <button class="btn ghost" type="button" @click="backfill">回填历史汇总</button>
      </div>
    </header>

    <p class="overview-meta">
      统计日期 {{ overview.date || '—' }} · {{ overview.criteria_note || '口径加载中' }}
      <span v-if="overview.generated_at">· 汇总生成于 {{ overview.generated_at }}</span>
    </p>

    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th>片区</th><th>当日新增</th><th>待处理</th><th>异常量</th><th>告警待处理</th><th>缺陷待处理</th><th>明细</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in regionRows" :key="row.region">
          <td>{{ row.region }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
          <td>{{ row.alarm_pending }}</td>
          <td>{{ row.defect_pending }}</td>
          <td><button class="link" type="button" @click="openDetail(row.region)">查看明细</button></td>
        </tr>
        <tr v-if="!regionRows.length">
          <td colspan="7" class="empty-state">该日期暂无已落库的片区汇总</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>两处口径打架时以概览为准；历史概览沿用生成时的统计口径，不按新口径重算。</span>
      <span v-if="message" class="error-text">{{ message }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { fetchJson, request } from '@/api/client'

type RegionRow = {
  region: string
  created: number
  pending: number
  abnormal: number
  alarm_pending: number
  defect_pending: number
}

type Overview = {
  date: string
  criteria_version: number
  criteria_note: string
  generated_at: string
  cards: { label: string; value: number }[]
  regions: RegionRow[]
}

const router = useRouter()
const route = useRoute()

const overview = ref<Overview>({
  date: '',
  criteria_version: 0,
  criteria_note: '',
  generated_at: '',
  cards: [],
  regions: [],
})
const cards = ref<Overview['cards']>([])
const regionRows = ref<RegionRow[]>([])
const queryDate = ref(String(route.query.day ?? ''))
const message = ref('')

async function reload() {
  message.value = ''
  const query = queryDate.value ? `?day=${queryDate.value}` : ''
  try {
    const payload = await fetchJson<Overview>(`/api/overview${query}`)
    overview.value = payload
    cards.value = payload.cards
    regionRows.value = payload.regions
    queryDate.value = payload.date
  } catch (error) {
    cards.value = []
    regionRows.value = []
    message.value = error instanceof Error ? error.message : '运营概览读取失败'
  }
}

async function backfill() {
  message.value = ''
  try {
    const response = await request('/api/overview/backfill', { method: 'POST' })
    const payload = await response.json()
    message.value = payload.message ?? '存量汇总已回填'
    await reload()
  } catch (error) {
    message.value = error instanceof Error ? error.message : '存量汇总回填失败'
  }
}

function openDetail(region: string) {
  void router.push({ path: '/overview/detail', query: { day: overview.value.date, region } })
}

onMounted(reload)
</script>

<style scoped>
.page-actions { display: flex; gap: 8px; align-items: center; }
.date-input { border: 1px solid var(--border); border-radius: 6px; padding: 6px 8px; }
.overview-meta { color: var(--muted); font-size: 12px; margin: 0 0 12px; }
</style>
