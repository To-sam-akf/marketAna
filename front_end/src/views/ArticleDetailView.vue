<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { ArticleDetail, Direction } from '../api/types'
import { getArticleDetail } from '../api/client'
import { DIRECTION_CONFIG } from '../api/types'
import LoadingState from '../components/common/LoadingState.vue'
import ErrorState from '../components/common/ErrorState.vue'

const route = useRoute()
const router = useRouter()
const detail = ref<ArticleDetail | null>(null)
const loading = ref(true)
const error = ref('')

const articleId = computed(() => Number(route.params.id))

async function fetchData() {
  loading.value = true
  error.value = ''
  try {
    const res = await getArticleDetail(articleId.value)
    if (res.code === 0) {
      detail.value = res.data
    } else {
      error.value = res.message || '加载失败'
    }
  } catch (e) {
    error.value = '网络错误'
  } finally {
    loading.value = false
  }
}

function goBack() {
  router.push('/articles')
}

const analysisResults = computed(() => detail.value?.analysis_results ?? (detail.value?.analysis_result ? [detail.value.analysis_result] : []))

function directionConfig(direction: string) {
  return DIRECTION_CONFIG[direction as Direction]
}

function methodLabel(method: string): string {
  if (method === 'rule') return '规则引擎'
  if (method === 'llm') return '大模型'
  if (method === 'manual') return '人工'
  return method
}

function statusLabel(status: number): string {
  const map: Record<string, string> = {
    '-1': '处理失败', '0': '未处理', '1': '解析完成', '2': '清洗完成',
    '3': '规则识别完成', '4': 'LLM 推理完成', '5': '已入库',
  }
  return map[String(status)] ?? '未知'
}

onMounted(fetchData)
</script>

<template>
  <div class="detail-page">
    <button class="back-btn" @click="goBack">← 返回资讯列表</button>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :message="error" :on-retry="fetchData" />

    <template v-else-if="detail">
      <!-- 文章头部 -->
      <div class="article-header">
        <h1 class="article-title">{{ detail.article.title }}</h1>
        <div class="article-meta">
          <span class="meta-item">来源：{{ detail.article.source || '未知' }}</span>
          <span class="meta-item">公司：{{ detail.article.company || '未知' }}</span>
          <span class="meta-item">时间：{{ detail.article.publish_time?.slice(0, 10) || '未知' }}</span>
          <span class="meta-item">
            状态：
            <span class="status-badge" :class="detail.article.status === 5 ? 'status-success' : 'status-fail'">
              {{ statusLabel(detail.article.status) }}
            </span>
          </span>
        </div>
      </div>

      <!-- 分析结果卡片 -->
      <div v-if="analysisResults.length" class="section-card result-card">
        <h2 class="section-title">分析结果</h2>
        <div class="results-table">
          <div class="results-head">
            <span>品种</span>
            <span>方向</span>
            <span>置信度</span>
            <span>方式</span>
            <span>状态</span>
          </div>
          <div
            v-for="result in analysisResults"
            :key="result.id ?? `${result.product}-${result.contract ?? ''}`"
            class="result-row"
          >
            <div class="product-cell">
              <strong>{{ result.product }}</strong>
              <span v-if="result.contract" class="contract-tag">{{ result.contract }}</span>
              <span v-if="result.is_primary" class="primary-tag">主</span>
            </div>
            <span
              v-if="directionConfig(result.direction)"
              class="direction-tag"
              :style="{ background: directionConfig(result.direction).bgColor, color: directionConfig(result.direction).color }"
            >
              {{ result.direction }}
            </span>
            <span class="confidence-value" :class="result.confidence < 0.5 ? 'low-confidence' : 'high-confidence'">
              {{ (result.confidence * 100).toFixed(0) }}%
            </span>
            <span>{{ methodLabel(result.analysis_method) }}</span>
            <span :class="result.need_manual_review ? 'review-text' : 'ok-text'">
              {{ result.need_manual_review ? '待确认' : '已确认' }}
            </span>
            <p v-if="result.reason" class="result-reason">{{ result.reason }}</p>
          </div>
        </div>
      </div>

      <div v-else class="section-card">
        <h2 class="section-title">分析结果</h2>
        <p class="no-data">暂无分析结果</p>
      </div>

      <!-- 清洗文本 -->
      <div v-if="detail.text?.cleaned_text" class="section-card">
        <h2 class="section-title">清洗文本</h2>
        <p class="cleaned-text">{{ detail.text.cleaned_text }}</p>
      </div>

      <!-- 原始文本 -->
      <div v-if="detail.text?.raw_text" class="section-card">
        <h2 class="section-title">原始文本
          <span class="text-meta">（{{ detail.text.parser_type }} · {{ detail.text.raw_length }}字 → {{ detail.text.cleaned_length }}字）</span>
        </h2>
        <pre class="raw-text">{{ detail.text.raw_text }}</pre>
      </div>

    </template>
  </div>
</template>

<style scoped>
.detail-page {
  max-width: 860px;
}

.back-btn {
  background: none;
  border: 1px solid #ddd;
  border-radius: 6px;
  padding: 6px 14px;
  font-size: 13px;
  color: #666;
  cursor: pointer;
  margin-bottom: 20px;
  transition: all 0.2s;
}

.back-btn:hover {
  border-color: #e74c3c;
  color: #e74c3c;
}

.article-header {
  margin-bottom: 24px;
}

.article-title {
  font-size: 22px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0 0 12px;
  line-height: 1.4;
}

.article-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.meta-item {
  font-size: 13px;
  color: #888;
}

.status-badge {
  padding: 1px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.status-success {
  background: #e8f5e9;
  color: #27ae60;
}

.status-fail {
  background: #fce8e6;
  color: #e74c3c;
}

/* 卡片通用 */
.section-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px 24px;
  border: 1px solid #f0f0f0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  margin-bottom: 16px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #1a1a2e;
  margin: 0 0 16px;
}

.text-meta {
  font-size: 12px;
  font-weight: 400;
  color: #aaa;
  margin-left: 8px;
}

/* 分析结果 */
.result-card {
  border-left: 4px solid #e74c3c;
}

.results-table {
  display: grid;
  gap: 8px;
}

.results-head,
.result-row {
  display: grid;
  grid-template-columns: minmax(140px, 1.4fr) minmax(76px, 0.7fr) minmax(74px, 0.7fr) minmax(82px, 0.8fr) minmax(72px, 0.7fr);
  gap: 12px;
  align-items: center;
}

.results-head {
  font-size: 12px;
  color: #999;
  padding: 0 10px 4px;
}

.result-row {
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  padding: 10px;
  font-size: 14px;
}

.product-cell {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  color: #1a1a2e;
}

.contract-tag,
.primary-tag {
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 12px;
  font-weight: 600;
}

.contract-tag {
  background: #f5f6fa;
  color: #666;
}

.primary-tag {
  background: #fce8e6;
  color: #e74c3c;
}

.direction-tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 700;
  width: fit-content;
}

.confidence-value {
  font-size: 15px;
  font-weight: 700;
}

.high-confidence {
  color: #27ae60;
}

.low-confidence {
  color: #e74c3c;
}

.review-text {
  color: #e74c3c;
  font-weight: 600;
}

.ok-text {
  color: #27ae60;
}

.result-reason {
  grid-column: 1 / -1;
  font-size: 13px;
  color: #333;
  margin: 2px 0 0;
  line-height: 1.6;
}

@media (max-width: 720px) {
  .results-head {
    display: none;
  }

  .result-row {
    grid-template-columns: 1fr 1fr;
  }
}

/* 文本 */
.cleaned-text {
  font-size: 14px;
  color: #333;
  line-height: 1.8;
  margin: 0;
}

.raw-text {
  font-size: 13px;
  color: #555;
  line-height: 1.6;
  background: #f8f9fa;
  padding: 12px 16px;
  border-radius: 8px;
  white-space: pre-wrap;
  word-wrap: break-word;
  max-height: 300px;
  overflow-y: auto;
  margin: 0;
}

.no-data {
  color: #999;
  font-size: 14px;
  margin: 0;
}
</style>
