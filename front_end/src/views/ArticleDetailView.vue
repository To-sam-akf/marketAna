<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { ArticleDetail } from '../api/types'
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

const dirConfig = computed(() => {
  const d = detail.value?.analysis_result?.direction
  return d && DIRECTION_CONFIG[d as keyof typeof DIRECTION_CONFIG]
    ? DIRECTION_CONFIG[d as '看涨' | '看跌' | '中性']
    : null
})

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
      <div v-if="detail.analysis_result" class="section-card result-card">
        <h2 class="section-title">分析结果</h2>
        <div class="result-grid">
          <div class="result-item">
            <span class="result-label">品种</span>
            <span class="result-value product-name">{{ detail.analysis_result.product }}</span>
          </div>
          <div class="result-item">
            <span class="result-label">方向</span>
            <span
              v-if="dirConfig"
              class="result-value direction-tag"
              :style="{ background: dirConfig.bgColor, color: dirConfig.color }"
            >
              {{ detail.analysis_result.direction }}
            </span>
          </div>
          <div class="result-item">
            <span class="result-label">置信度</span>
            <span class="result-value confidence-value" :class="detail.analysis_result.confidence < 0.5 ? 'low-confidence' : 'high-confidence'">
              {{ (detail.analysis_result.confidence * 100).toFixed(0) }}%
            </span>
          </div>
          <div class="result-item">
            <span class="result-label">分析方式</span>
            <span class="result-value">{{ detail.analysis_result.analysis_method === 'rule' ? '规则引擎' : detail.analysis_result.analysis_method === 'llm' ? '大模型' : '手动' }}</span>
          </div>
        </div>

        <!-- 待人工确认标记 -->
        <div v-if="detail.analysis_result.need_manual_review" class="review-warning">
          ⚠️ 该结果置信度较低，<strong>待人工确认</strong>
        </div>

        <div v-if="detail.analysis_result.reason" class="reason-box">
          <span class="reason-label">理由：</span>
          <p class="reason-text">{{ detail.analysis_result.reason }}</p>
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

.result-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.result-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.result-label {
  font-size: 12px;
  color: #999;
}

.result-value {
  font-size: 18px;
  font-weight: 700;
  color: #1a1a2e;
}

.product-name {
  color: #e74c3c;
}

.direction-tag {
  display: inline-block;
  padding: 2px 14px;
  border-radius: 6px;
  font-size: 16px;
  font-weight: 700;
  width: fit-content;
}

.confidence-value {
  font-size: 20px;
}

.high-confidence {
  color: #27ae60;
}

.low-confidence {
  color: #e74c3c;
}

.review-warning {
  background: #fff3cd;
  border: 1px solid #ffc107;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 14px;
  color: #856404;
  margin-bottom: 14px;
}

.reason-box {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 12px 16px;
}

.reason-label {
  font-size: 13px;
  font-weight: 600;
  color: #555;
}

.reason-text {
  font-size: 14px;
  color: #333;
  margin: 6px 0 0;
  line-height: 1.6;
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
