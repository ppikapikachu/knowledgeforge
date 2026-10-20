<script setup lang="ts">
/**
 * 出题策略管理
 * 后端 API:
 *   GET  /question-generation/policies/effective?question_bank_id=
 *   PUT  /question-generation/policies/global
 *   PUT  /question-generation/policies/question-banks/{id}
 *   DELETE /question-generation/policies/question-banks/{id}
 *
 * 后端实际约束: target_stock 1-500, usage_extra_ratio 0-2, max_per_knowledge_per_task 1-50
 * 权重校验: stock_weight + usage_weight + importance_weight === 100
 */
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  getEffectivePolicy,
  saveGlobalPolicy,
  saveQuestionBankPolicy,
  deleteQuestionBankPolicy,
} from '@/api/questionDemand'
import { getQuestionBankList } from '@/api/questionBank'
import type { GenerationPolicy, EffectivePolicyResponse, ImportanceLevelInfo } from '@/types/questionDemand'
import type { QuestionBank } from '@/types/questionManagement'
import {
  POLICY_CONSTRAINTS,
  POLICY_SOURCE_LABELS,
  IMPORTANCE_LEVELS,
} from '@/constants/questionDemand'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Settings, Save, RefreshCw, Info, ArrowLeft } from 'lucide-vue-next'

const router = useRouter()

const banks = ref<QuestionBank[]>([])
const selectedBankId = ref<number | null>(null)
const loading = ref(false)
const saving = ref(false)

const effectiveData = ref<EffectivePolicyResponse | null>(null)
const importanceLevels = ref<ImportanceLevelInfo[]>([])

const form = ref<Omit<GenerationPolicy, 'version' | 'updated_at'>>({
  stock_weight: 50,
  usage_weight: 30,
  importance_weight: 20,
  target_stock: 20,
  usage_window_days: 30,
  recent_answers_per_question_target: 3,
  usage_extra_ratio: 0.5,
  max_per_knowledge_per_task: 10,
  min_demand_score: 0.15,
  is_enabled: true,
})

const weightSum = computed(() =>
  form.value.stock_weight + form.value.usage_weight + form.value.importance_weight,
)
const weightValid = computed(() => weightSum.value === 100)
const weightDiff = computed(() => weightSum.value - 100)

const sourceLabel = computed(() => {
  if (!effectiveData.value) return ''
  return POLICY_SOURCE_LABELS[effectiveData.value.source] || effectiveData.value.source
})

const isQuestionBankScope = computed(() => selectedBankId.value !== null)
const isOverride = computed(() => effectiveData.value?.source === 'question_bank_override')

async function loadBanks() {
  try {
    const res = await getQuestionBankList({ page: 1, page_size: 100 })
    banks.value = res.data.items
  } catch {
    ElMessage.error('题库列表加载失败')
  }
}

async function loadPolicy() {
  loading.value = true
  try {
    const res = await getEffectivePolicy(selectedBankId.value)
    effectiveData.value = res.data
    importanceLevels.value = res.data.importance_levels || IMPORTANCE_LEVELS.map((l) => ({ ...l }))

    const p = res.data.policy
    form.value = {
      stock_weight: p.stock_weight,
      usage_weight: p.usage_weight,
      importance_weight: p.importance_weight,
      target_stock: p.target_stock,
      usage_window_days: p.usage_window_days,
      recent_answers_per_question_target: p.recent_answers_per_question_target,
      usage_extra_ratio: p.usage_extra_ratio,
      max_per_knowledge_per_task: p.max_per_knowledge_per_task,
      min_demand_score: p.min_demand_score,
      is_enabled: p.is_enabled,
    }
  } catch {
    ElMessage.error('策略加载失败')
  } finally {
    loading.value = false
  }
}

function handleScopeChange() {
  loadPolicy()
}

async function handleSave() {
  if (!weightValid.value) {
    ElMessage.error(`权重合计必须为 100，当前为 ${weightSum.value}，差额 ${weightDiff.value > 0 ? '+' : ''}${weightDiff.value}`)
    return
  }

  saving.value = true
  try {
    if (isQuestionBankScope.value && selectedBankId.value) {
      await saveQuestionBankPolicy(selectedBankId.value, { ...form.value })
      ElMessage.success('题库策略保存成功')
    } else {
      await saveGlobalPolicy({ ...form.value })
      ElMessage.success('全局策略保存成功')
    }
    await loadPolicy()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDeleteOverride() {
  if (!selectedBankId.value || !isOverride.value) return

  try {
    await ElMessageBox.confirm(
      '删除后该题库将恢复使用全局默认策略，是否继续？',
      '恢复使用全局策略',
      { confirmButtonText: '确认恢复', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }

  saving.value = true
  try {
    await deleteQuestionBankPolicy(selectedBankId.value)
    ElMessage.success('已恢复使用全局策略')
    await loadPolicy()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '操作失败')
  } finally {
    saving.value = false
  }
}

function handleReset() {
  loadPolicy()
}

onMounted(async () => {
  await Promise.all([loadBanks(), loadPolicy()])
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>出题策略管理</h2>
        <p class="description">配置全局默认策略或为特定题库设置独立策略覆盖</p>
      </div>
      <el-button @click="router.back()">
        <ArrowLeft :size="16" style="margin-right: 4px;" />
        返回
      </el-button>
    </div>

    <!-- 策略范围选择 -->
    <div class="filter-toolbar">
      <span class="scope-label">策略作用范围：</span>
      <el-select
        v-model="selectedBankId"
        placeholder="全局默认策略"
        clearable
        style="width: 240px;"
        @change="handleScopeChange"
      >
        <el-option label="全局默认策略" :value="null" />
        <el-option
          v-for="b in banks"
          :key="b.id"
          :label="b.name"
          :value="b.id"
        />
      </el-select>
      <el-button @click="handleReset">
        <RefreshCw :size="16" style="margin-right: 4px;" />
        刷新
      </el-button>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="card">
      <div class="card-body">
        <el-skeleton :rows="10" animated />
      </div>
    </div>

    <template v-else-if="effectiveData">
      <!-- 来源提示 -->
      <div class="card">
        <div class="card-body">
          <div class="source-info">
            <Info :size="18" style="flex-shrink: 0;" />
            <div>
              <div class="source-label">
                当前生效：{{ sourceLabel }}
                <el-tag v-if="effectiveData.policy.version" size="small" type="info" style="margin-left: 8px;">
                  v{{ effectiveData.policy.version }}
                </el-tag>
              </div>
              <div class="source-detail">
                {{ isOverride
                  ? `题库「${banks.find(b => b.id === selectedBankId)?.name}」正在使用独立策略覆盖全局策略`
                  : '所有题库继承此全局默认策略'
                }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 策略表单 -->
      <div class="card" style="margin-top: 16px;">
        <div class="card-header">策略参数</div>
        <div class="card-body">
          <el-form :model="form" label-width="180px" label-position="right" style="max-width: 600px;">
            <!-- 权重 -->
            <div class="section-title">需求分权重（合计必须等于 100）</div>

            <el-form-item label="库存缺口权重">
              <div class="input-row">
                <el-input-number v-model="form.stock_weight" :min="0" :max="100" style="width: 120px;" />
                <span class="unit">分</span>
              </div>
            </el-form-item>

            <el-form-item label="使用频率权重">
              <div class="input-row">
                <el-input-number v-model="form.usage_weight" :min="0" :max="100" style="width: 120px;" />
                <span class="unit">分</span>
              </div>
            </el-form-item>

            <el-form-item label="重要程度权重">
              <div class="input-row">
                <el-input-number v-model="form.importance_weight" :min="0" :max="100" style="width: 120px;" />
                <span class="unit">分</span>
              </div>
            </el-form-item>

            <!-- 权重合计 -->
            <el-form-item>
              <div class="weight-sum" :class="weightValid ? 'valid' : 'invalid'">
                权重合计：<strong>{{ weightSum }}</strong>
                <template v-if="!weightValid">
                  <span class="diff">（{{ weightDiff > 0 ? '+' : '' }}{{ weightDiff }}）</span>
                  <span class="hint">需为 100</span>
                </template>
                <span v-else class="ok-hint">✓ 合法</span>
              </div>
            </el-form-item>

            <el-divider />

            <div class="section-title">需求计算参数</div>

            <el-form-item label="每个知识点目标库存">
              <el-input-number v-model="form.target_stock" :min="1" :max="500" :step="1" style="width: 140px;" />
            </el-form-item>

            <el-form-item label="使用统计窗口（天）">
              <el-input-number v-model="form.usage_window_days" :min="1" :max="365" :step="1" style="width: 140px;" />
            </el-form-item>

            <el-form-item label="每题目标答题次数">
              <el-input-number v-model="form.recent_answers_per_question_target" :min="1" :max="100" :step="1" style="width: 140px;" />
            </el-form-item>

            <el-form-item label="单任务单知识点上限">
              <el-input-number v-model="form.max_per_knowledge_per_task" :min="1" :max="50" :step="1" style="width: 140px;" />
            </el-form-item>

            <el-form-item label="使用频率额外系数">
              <el-input-number v-model="form.usage_extra_ratio" :min="0" :max="2" :step="0.1" :precision="2" style="width: 140px;" />
            </el-form-item>

            <el-form-item label="最低需求分阈值">
              <el-input-number v-model="form.min_demand_score" :min="0" :max="1" :step="0.05" :precision="2" style="width: 140px;" />
            </el-form-item>

            <el-form-item label="启用智能分配">
              <el-switch v-model="form.is_enabled" />
              <span class="switch-hint">{{ form.is_enabled ? '已启用' : '已停用，auto 模式不可用' }}</span>
            </el-form-item>

            <el-form-item>
              <el-button type="primary" :loading="saving" :disabled="!weightValid" @click="handleSave">
                <Save :size="16" style="margin-right: 4px;" />
                保存策略
              </el-button>
              <el-button
                v-if="isQuestionBankScope && isOverride"
                type="danger"
                plain
                :loading="saving"
                @click="handleDeleteOverride"
              >
                恢复使用全局策略
              </el-button>
            </el-form-item>
          </el-form>
        </div>
      </div>

      <!-- 重要程度映射说明 -->
      <div class="card" style="margin-top: 16px;">
        <div class="card-header">
          <Info :size="16" style="margin-right: 6px;" />
          策略说明（只读）
        </div>
        <div class="card-body">
          <pre class="formula-text">需求分 = 库存缺口分 × 库存权重
       + 使用压力分 × 使用权重
       + 重要程度分 × 重要程度权重

库存缺口分 = clamp((目标库存 - 已承诺数量) / 目标库存, 0, 1)
使用压力分 = 近期覆盖率与近期使用强度的综合值
重要程度分 = 由知识点 importance_level 映射得出</pre>

          <div class="importance-map">
            <div class="map-title">重要程度分值映射：</div>
            <div v-for="level in importanceLevels" :key="level.value" class="map-item">
              <span class="map-value">{{ level.value }}</span>
              <span class="map-label">{{ level.label }}</span>
              <span class="map-score">{{ level.score.toFixed(2) }}</span>
              <span class="map-desc">{{ level.description }}</span>
            </div>
          </div>
          <div class="formula-note">
            需求分和分配数量由后端计算，前端仅展示参数和结果，不复制算法。
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.scope-label {
  font-size: 14px;
  color: var(--color-muted-foreground);
  margin-right: 8px;
}

.source-info {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.source-label {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-foreground);
  display: flex;
  align-items: center;
}

.source-detail {
  font-size: 13px;
  color: var(--color-muted-foreground);
  margin-top: 4px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-muted-foreground);
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border);
}

.input-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.unit {
  font-size: 13px;
  color: var(--color-muted-foreground);
}

.weight-sum {
  font-size: 14px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  gap: 6px;
}

.weight-sum.valid {
  background: #ECFDF5;
  color: #059669;
}

.weight-sum.invalid {
  background: #FEF2F2;
  color: #DC2626;
}

.weight-sum .diff {
  font-weight: 600;
}

.weight-sum .hint,
.weight-sum .ok-hint {
  font-size: 12px;
  opacity: 0.8;
}

.switch-hint {
  margin-left: 12px;
  font-size: 13px;
  color: var(--color-muted-foreground);
}

.formula-text {
  margin: 0;
  font-family: 'Courier New', Courier, monospace;
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.8;
  color: var(--color-foreground);
  background: var(--color-muted);
  padding: 16px;
  border-radius: var(--radius-md);
}

.importance-map {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.map-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-muted-foreground);
}

.map-item {
  display: flex;
  gap: 12px;
  align-items: center;
  font-size: 13px;
  padding: 6px 12px;
  background: var(--color-muted);
  border-radius: var(--radius-sm);
}

.map-value {
  font-family: monospace;
  width: 100px;
  color: var(--color-foreground);
  font-weight: 600;
}

.map-label {
  width: 80px;
  color: var(--color-foreground);
}

.map-score {
  width: 50px;
  text-align: right;
  color: var(--color-primary);
  font-weight: 600;
}

.map-desc {
  color: var(--color-muted-foreground);
  flex: 1;
}

.formula-note {
  margin-top: 12px;
  padding: 10px 12px;
  background: #FFFBEB;
  border-radius: var(--radius-md);
  font-size: 12px;
  color: #92400E;
}
</style>
