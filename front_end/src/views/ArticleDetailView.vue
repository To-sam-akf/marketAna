<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { ArticleDetail, Direction, AnalysisResultItem, ReviewQueueItem } from '../api/types'
import { confirmResult, createManualConclusion, getArticleDetail, rejectReviewItem, runArticleTask } from '../api/client'
import { DIRECTION_CONFIG } from '../api/types'
import LoadingState from '../components/common/LoadingState.vue'
import ErrorState from '../components/common/ErrorState.vue'

const route = useRoute()
const router = useRouter()
const detail = ref<ArticleDetail | null>(null)
const loading = ref(true)
const error = ref('')
const confirming = ref(false)
const confirmDirection = ref<Direction>('中性')
const confirmReason = ref('')
const reviewBusy = ref<Record<number, string>>({})
const reviewError = ref<Record<number, string>>({})
const openConclusion = ref<Record<number, boolean>>({})
const reviewDirection = ref<Record<number, Direction>>({})
const reviewReason = ref<Record<number, string>>({})
const reviewEvidence = ref<Record<number, string>>({})

const articleId = computed(() => Number(route.params.id))
const activeProduct = computed(() => (route.query.product as string) || '')

// 所有分析结果
const allResults = computed(() =>
  detail.value?.analysis_results ?? (
    detail.value?.analysis_result ? [detail.value.analysis_result as unknown as AnalysisResultItem] : []
  )
)

// 当前聚焦品种的分析结果
const activeResult = computed(() => {
  if (!activeProduct.value) return allResults.value[0] ?? null
  return allResults.value.find((r) => r.product === activeProduct.value) ?? allResults.value[0] ?? null
})

function hasVerifiedEvidence(result: AnalysisResultItem) {
  const evidence = result.evidence
  return !!(
    evidence?.refined_text ||
    evidence?.cleaned_text ||
    evidence?.excerpts?.some((item) => item.quote?.trim())
  )
}

function isPendingConclusion(result: AnalysisResultItem) {
  return result.need_manual_review && !hasVerifiedEvidence(result)
}

const activeIsPendingConclusion = computed(() =>
  activeResult.value ? isPendingConclusion(activeResult.value) : false,
)

// 结论依据：优先使用后端按品种切分后的正文
const evidenceText = computed(() => {
  return activeResult.value?.evidence?.refined_text ||
    activeResult.value?.evidence?.cleaned_text ||
    activeResult.value?.evidence?.excerpts?.map((item) => item.quote).filter(Boolean).join('\n\n') ||
    ''
})

// 其他品种（本研报还覆盖）
const otherResults = computed(() =>
  allResults.value.filter((r) => r.product !== activeResult.value?.product)
)

function dirCfg(direction: string) {
  return DIRECTION_CONFIG[direction as Direction]
}

function methodLabel(method: string): string {
  if (method === 'rule') return '规则引擎'
  if (method === 'llm') return '大模型'
  if (method === 'manual') return '人工'
  return method
}

function switchProduct(product: string) {
  router.push({ query: { product } })
}

function goBack() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/products')
  }
}

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

async function submitConfirmation() {
  const result = activeResult.value
  if (!result?.id) return
  confirming.value = true
  try {
    await confirmResult(result.id, {
      product: result.product,
      product_key: result.product_key,
      direction: confirmDirection.value,
      reason: confirmReason.value || result.reason || undefined,
      confidence: Math.max(0, Math.min(1, result.confidence)),
      confirmed_by: 'frontend',
    })
    await fetchData()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '确认失败'
  } finally {
    confirming.value = false
  }
}

function reviewStatusLabel(status: string) {
  if (status === 'rejected') return '已驳回'
  if (status === 'resolved') return '已创建人工结论'
  return '待审核'
}

function triggerEvidence(item: ReviewQueueItem): string[] {
  const value = item.evidence
  if (!value) return []
  if (typeof value === 'string') return [value]
  if (Array.isArray(value)) {
    return value.flatMap((entry) => {
      if (typeof entry === 'string') return [entry]
      if (entry && typeof entry === 'object' && 'quote' in entry) return [String(entry.quote || '')]
      return []
    }).filter(Boolean)
  }
  if (typeof value === 'object') {
    const record = value as Record<string, unknown>
    const excerpts = Array.isArray(record.excerpts) ? record.excerpts : []
    const quotes = excerpts.flatMap((entry) => {
      if (typeof entry === 'string') return [entry]
      if (entry && typeof entry === 'object' && 'quote' in entry) {
        return [String((entry as Record<string, unknown>).quote || '')]
      }
      return []
    }).filter(Boolean)
    if (quotes.length) return quotes
    for (const key of ['quote', 'excerpt', 'text', 'raw']) {
      if (typeof record[key] === 'string' && record[key]) return [record[key] as string]
    }
  }
  return []
}

async function rejectItem(item: ReviewQueueItem) {
  reviewBusy.value[item.id] = '正在驳回…'
  reviewError.value[item.id] = ''
  try {
    await rejectReviewItem(item.id, '误识别/驳回')
    await fetchData()
  } catch (cause) {
    reviewError.value[item.id] = cause instanceof Error ? cause.message : '驳回失败'
  } finally {
    delete reviewBusy.value[item.id]
  }
}

async function reparseItem(item: ReviewQueueItem) {
  reviewBusy.value[item.id] = '正在重新解析…'
  reviewError.value[item.id] = ''
  try {
    await runArticleTask(articleId.value)
    await fetchData()
  } catch (cause) {
    reviewError.value[item.id] = cause instanceof Error ? cause.message : '重新解析失败'
  } finally {
    delete reviewBusy.value[item.id]
  }
}

function showConclusionForm(item: ReviewQueueItem) {
  openConclusion.value[item.id] = true
  reviewDirection.value[item.id] ||= '中性'
}

function isConclusionComplete(item: ReviewQueueItem) {
  return !!reviewDirection.value[item.id] && !!reviewReason.value[item.id]?.trim() && !!reviewEvidence.value[item.id]?.trim()
}

async function submitManualConclusion(item: ReviewQueueItem) {
  if (!isConclusionComplete(item)) return
  reviewBusy.value[item.id] = '正在创建…'
  reviewError.value[item.id] = ''
  try {
    await createManualConclusion(item.id, {
      direction: reviewDirection.value[item.id] || '中性',
      reason: (reviewReason.value[item.id] || '').trim(),
      evidence: (reviewEvidence.value[item.id] || '').trim(),
      product: item.product || undefined,
      product_key: item.product_key || undefined,
    })
    await fetchData()
  } catch (cause) {
    reviewError.value[item.id] = cause instanceof Error ? cause.message : '创建人工结论失败'
  } finally {
    delete reviewBusy.value[item.id]
  }
}

onMounted(fetchData)
</script>

<template>
  <div class="detail-page">
    <button class="back-btn" @click="goBack">← 返回</button>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :message="error" :on-retry="fetchData" />

    <template v-else-if="detail && activeResult">
      <!-- 研报标题 -->
      <div class="article-header">
        <h1 class="article-title">{{ detail.article.title }}</h1>
        <div class="article-meta">
          <span>{{ detail.article.source || '未知来源' }}</span>
          <span class="meta-divider">/</span>
          <span>{{ detail.article.company || '未知公司' }}</span>
          <span class="meta-divider">/</span>
          <span>{{ detail.article.publish_time?.slice(0, 10) || '未知日期' }}</span>
        </div>
      </div>

      <!-- 当前品种观点摘要（核心卡片） -->
      <div class="focus-card">
        <div class="focus-top">
          <span class="focus-product">{{ activeResult.product }}</span>
          <span v-if="activeIsPendingConclusion" class="focus-direction pending-direction">
            待判断
          </span>
          <span
            v-else-if="dirCfg(activeResult.direction)"
            class="focus-direction"
            :style="{ background: dirCfg(activeResult.direction).bgColor, color: dirCfg(activeResult.direction).color }"
          >
            {{ activeResult.direction }}
          </span>
          <span
            v-if="!activeIsPendingConclusion"
            class="focus-confidence"
            :class="activeResult.confidence >= 0.5 ? 'conf-high' : 'conf-low'"
          >
            {{ (activeResult.confidence * 100).toFixed(0) }}%
          </span>
          <span class="focus-method">{{ methodLabel(activeResult.analysis_method) }}</span>
          <span v-if="activeResult.need_manual_review" class="focus-review">待人工确认</span>
        </div>

        <div v-if="activeIsPendingConclusion" class="rule-suggestion">
          规则建议：
          <span v-if="dirCfg(activeResult.direction)" :style="{ color: dirCfg(activeResult.direction).color }">
            {{ activeResult.direction }}
          </span>
          · {{ (activeResult.confidence * 100).toFixed(0) }}%
          <span class="suggestion-note">（尚无本品种可验证证据）</span>
        </div>

        <p class="focus-reason">
          {{ activeIsPendingConclusion
            ? '当前无法形成正式结论，请结合原文完成人工确认。'
            : (activeResult.reason || activeResult.evidence?.summary || '暂无理由') }}
        </p>

        <div v-if="activeResult.need_manual_review" class="confirmation-box">
          <strong>人工确认</strong>
          <select v-model="confirmDirection" aria-label="确认方向">
            <option value="看涨">看涨</option>
            <option value="看跌">看跌</option>
            <option value="中性">中性</option>
          </select>
          <input v-model="confirmReason" placeholder="可选：补充确认理由">
          <button type="button" :disabled="confirming" @click="submitConfirmation">
            {{ confirming ? '提交中…' : '确认结果' }}
          </button>
        </div>

        <!-- 结论依据 -->
        <div v-if="evidenceText" class="evidence-section">
          <h3 class="evidence-heading">
            结论依据
            <span v-if="activeResult.evidence?.section_type === 'mixed'" class="evidence-badge">混合片段</span>
          </h3>
          <div class="refined-text">{{ evidenceText }}</div>
        </div>
      </div>

      <!-- 本研报还覆盖 -->
      <div v-if="otherResults.length" class="other-section">
        <h3 class="other-heading">本研报还覆盖</h3>
        <div class="other-list">
          <button
            v-for="result in otherResults"
            :key="result.product + (result.contract ?? '')"
            class="other-chip"
            @click="switchProduct(result.product)"
          >
            <span class="other-product">{{ result.product }}</span>
            <span v-if="isPendingConclusion(result)" class="other-direction pending-text">
              待判断
            </span>
            <span
              v-else-if="dirCfg(result.direction)"
              class="other-direction"
              :style="{ color: dirCfg(result.direction).color }"
            >
              {{ result.direction }}
            </span>
            <span v-if="!isPendingConclusion(result)" class="other-confidence" :class="result.confidence >= 0.5 ? 'conf-high' : 'conf-low'">
              {{ (result.confidence * 100).toFixed(0) }}%
            </span>
            <span v-else class="other-suggestion">
              建议{{ result.direction }} {{ (result.confidence * 100).toFixed(0) }}%
            </span>
          </button>
        </div>
      </div>

    </template>

    <!-- 无分析结果 -->
    <div v-else-if="detail && !allResults.length" class="review-empty-page">
      <div class="empty-card">
        <h1>{{ detail.article.title }}</h1>
        <p v-if="detail.review_queue?.length">
          当前没有正式分析结果，已有 {{ detail.review_queue.length }} 项进入人工复核队列。
        </p>
        <p v-else>暂无分析结果，可能仍在处理或原文未识别到有效品种。</p>
      </div>

      <section v-if="detail.review_queue?.length" class="manual-review-section">
        <div class="review-section-heading">
          <div>
            <h2>人工审核</h2>
            <p>逐项核对触发证据。只有方向、理由和证据均填写完整，才会生成正式结果。</p>
          </div>
          <span>{{ detail.review_queue.length }} 项</span>
        </div>

        <article v-for="(item, index) in detail.review_queue" :key="item.id" class="manual-review-card">
          <div class="review-item-heading">
            <div>
              <span class="review-index">#{{ index + 1 }}</span>
              <strong>{{ item.product || item.product_key || '未识别品种' }}</strong>
            </div>
            <span class="review-status" :class="`status-${item.status}`">{{ reviewStatusLabel(item.status) }}</span>
          </div>
          <p class="trigger-reason">触发原因：{{ item.reason }}</p>
          <div class="trigger-evidence">
            <strong>触发证据</strong>
            <blockquote v-for="(quote, quoteIndex) in triggerEvidence(item)" :key="quoteIndex">{{ quote }}</blockquote>
            <p v-if="!triggerEvidence(item).length">该项未返回可展示的原文片段，请重新解析或结合原文审核。</p>
          </div>

          <div v-if="item.status === 'pending'" class="review-actions">
            <button class="danger-button" type="button" :disabled="!!reviewBusy[item.id]" @click="rejectItem(item)">误识别/驳回</button>
            <button type="button" :disabled="!!reviewBusy[item.id]" @click="reparseItem(item)">重新解析</button>
            <button class="primary-action" type="button" :disabled="!!reviewBusy[item.id]" @click="showConclusionForm(item)">创建人工结论</button>
            <span v-if="reviewBusy[item.id]" class="operation-status">{{ reviewBusy[item.id] }}</span>
          </div>

          <form v-if="item.status === 'pending' && openConclusion[item.id]" class="manual-form" @submit.prevent="submitManualConclusion(item)">
            <label>方向
              <select v-model="reviewDirection[item.id]" required>
                <option value="看涨">看涨</option>
                <option value="看跌">看跌</option>
                <option value="中性">中性</option>
              </select>
            </label>
            <label>理由
              <textarea v-model="reviewReason[item.id]" required rows="3" placeholder="填写形成该方向判断的完整理由" />
            </label>
            <label>证据
              <textarea v-model="reviewEvidence[item.id]" required rows="4" placeholder="粘贴并说明支持结论的原文证据" />
            </label>
            <div class="form-actions">
              <button type="button" @click="openConclusion[item.id] = false">取消</button>
              <button class="primary-action" type="submit" :disabled="!isConclusionComplete(item) || !!reviewBusy[item.id]">创建正式结果</button>
            </div>
          </form>
          <p v-if="reviewError[item.id]" class="review-error">{{ reviewError[item.id] }}</p>
          <p v-if="item.status !== 'pending' && item.reviewed_at" class="review-audit">
            {{ item.reviewed_at.slice(0, 16).replace('T', ' ') }} · {{ item.reviewed_by || '审核人员' }}
          </p>
        </article>
      </section>
    </div>
  </div>
</template>

<style scoped>
.detail-page {
  max-width: 800px;
}

/* 返回按钮 */
.back-btn {
  background: none;
  border: 1px solid #ddd;
  border-radius: 6px;
  padding: 6px 14px;
  font-size: 13px;
  color: #666;
  cursor: pointer;
  margin-bottom: 16px;
  transition: all 0.15s;
}

.back-btn:hover {
  border-color: #e74c3c;
  color: #e74c3c;
}

/* 研报标题 */
.article-header {
  margin-bottom: 20px;
}

.article-title {
  font-size: 20px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0 0 8px;
  line-height: 1.4;
}

.article-meta {
  font-size: 13px;
  color: #888;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.meta-divider {
  color: #ddd;
}

/* 聚焦品种卡片 */
.focus-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px 24px;
  border: 1px solid #f0f0f0;
  border-left: 4px solid #e74c3c;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  margin-bottom: 16px;
}

.focus-top {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
}

.focus-product {
  font-size: 22px;
  font-weight: 700;
  color: #1a1a2e;
}

.focus-direction {
  display: inline-block;
  padding: 3px 12px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 700;
}

.pending-direction {
  background: #fff3d6;
  color: #9a6700;
}

.rule-suggestion {
  background: #fff8ed;
  border-radius: 6px;
  color: #5f6670;
  font-size: 13px;
  margin-bottom: 10px;
  padding: 8px 10px;
}

.suggestion-note {
  color: #999;
}

.focus-confidence {
  font-size: 18px;
  font-weight: 700;
}

.conf-high { color: #27ae60; }
.conf-low { color: #e74c3c; }

.focus-method {
  font-size: 12px;
  color: #999;
  background: #f5f6fa;
  padding: 2px 8px;
  border-radius: 4px;
}

.focus-review {
  font-size: 12px;
  font-weight: 600;
  color: #e74c3c;
  background: #fce8e6;
  padding: 2px 8px;
  border-radius: 4px;
}

.focus-reason {
  font-size: 15px;
  color: #333;
  line-height: 1.6;
  margin: 0 0 4px;
}

.confirmation-box {
  align-items: center;
  background: #fff8ed;
  border: 1px solid #f1d7a7;
  border-radius: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
  padding: 10px;
}

.confirmation-box select,
.confirmation-box input,
.confirmation-box button {
  border: 1px solid #d8c7a8;
  border-radius: 5px;
  min-height: 30px;
  padding: 4px 8px;
}

.confirmation-box input { flex: 1 1 220px; }
.confirmation-box button { background: #2367d1; color: white; cursor: pointer; }

/* 结论依据 */
.evidence-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}

.evidence-heading {
  font-size: 14px;
  font-weight: 600;
  color: #1a1a2e;
  margin: 0 0 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.evidence-badge {
  font-size: 12px;
  color: #999;
  background: #f5f6fa;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 500;
}

.refined-text {
  font-size: 14px;
  color: #333;
  line-height: 1.9;
  white-space: pre-line;
  word-wrap: break-word;
}

/* 本研报还覆盖 */
.other-section {
  background: #fff;
  border-radius: 12px;
  padding: 16px 20px;
  border: 1px solid #f0f0f0;
  margin-bottom: 16px;
}

.other-heading {
  font-size: 14px;
  font-weight: 600;
  color: #555;
  margin: 0 0 12px;
}

.other-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.other-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #f8f9fa;
  border: 1px solid #e8eaed;
  border-radius: 8px;
  padding: 6px 12px;
  cursor: pointer;
  transition: all 0.15s;
  font-size: 13px;
}

.other-chip:hover {
  background: #f0f0f0;
  border-color: #ccc;
}

.other-product {
  font-weight: 600;
  color: #1a1a2e;
}

.other-direction {
  font-weight: 600;
  font-size: 12px;
}

.other-confidence {
  font-size: 12px;
  font-weight: 700;
}

.pending-text {
  color: #9a6700;
}

.other-suggestion {
  color: #999;
  font-size: 11px;
}

/* 完整研报文本 */

/* 空状态 */
.empty-card {
  background: #fff;
  border-radius: 12px;
  padding: 40px;
  text-align: center;
  color: #999;
  font-size: 14px;
}

.review-empty-page { max-width: 900px; }
.manual-review-section { margin-top: 20px; }
.review-section-heading { align-items: flex-start; display: flex; justify-content: space-between; margin-bottom: 12px; }
.review-section-heading h2 { color: #1a1a2e; font-size: 20px; }
.review-section-heading p { color: #77808c; margin-top: 4px; }
.review-section-heading > span { background: #e9eef7; border-radius: 999px; color: #526173; font-weight: 600; padding: 3px 10px; }
.manual-review-card { background: #fff; border: 1px solid #e5e8ec; border-radius: 10px; margin-bottom: 12px; padding: 18px; text-align: left; }
.review-item-heading { align-items: center; display: flex; justify-content: space-between; }
.review-index { color: #98a0aa; margin-right: 8px; }
.review-status { border-radius: 999px; font-size: 12px; font-weight: 600; padding: 3px 9px; }
.status-pending { background: #fff3d6; color: #946200; }
.status-rejected { background: #f2f3f5; color: #69717b; }
.status-resolved { background: #e4f6e9; color: #26733b; }
.trigger-reason { color: #5f6670; margin: 9px 0; }
.trigger-evidence { background: #f7f8fa; border-radius: 7px; padding: 12px; }
.trigger-evidence blockquote { border-left: 3px solid #a9b5c5; color: #333; margin-top: 8px; padding-left: 10px; white-space: pre-wrap; }
.trigger-evidence p { color: #8a919a; margin-top: 6px; }
.review-actions, .form-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.review-actions button, .form-actions button { background: #fff; border: 1px solid #cfd5dd; border-radius: 5px; cursor: pointer; min-height: 34px; padding: 6px 12px; }
.review-actions .danger-button { border-color: #e0a5a0; color: #b33b31; }
.review-actions .primary-action, .form-actions .primary-action { background: #2367d1; border-color: #2367d1; color: #fff; }
.review-actions button:disabled, .form-actions button:disabled { cursor: not-allowed; opacity: .5; }
.operation-status { align-self: center; color: #6d7681; }
.manual-form { background: #f8faff; border: 1px solid #dce5f4; border-radius: 8px; display: grid; gap: 10px; margin-top: 12px; padding: 14px; }
.manual-form label { color: #3e4752; display: grid; font-weight: 600; gap: 5px; }
.manual-form select, .manual-form textarea { background: #fff; border: 1px solid #cbd3de; border-radius: 5px; font: inherit; padding: 8px; resize: vertical; }
.form-actions { justify-content: flex-end; margin-top: 0; }
.review-error { color: #b33b31; margin-top: 8px; }
.review-audit { color: #8a919a; font-size: 12px; margin-top: 10px; }
</style>
