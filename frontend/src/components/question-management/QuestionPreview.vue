<script setup lang="ts">
/**
 * 题目预览组件（审核/详情共用）
 * 以纯文本 pre-wrap 展示题干/解析，不注入 HTML，规避 XSS。
 */
import { computed } from 'vue'
import type { Question } from '@/types/question'
import {
  QUESTION_TYPE_LABELS,
  DIFFICULTY_LABELS,
  DIFFICULTY_CLASSES,
  isChoiceType,
} from '@/constants/questionManagement'
import QuestionStatusTag from './QuestionStatusTag.vue'

const props = defineProps<{
  question: Question
  bankName?: string
  knowledgeNames?: string[]
}>()

const sortedOptions = computed(() => {
  return [...(props.question.options || [])].sort((a, b) => a.sort_order - b.sort_order)
})

const answerText = computed(() => {
  const q = props.question
  if (q.question_type === 'TRUE_FALSE') {
    return q.answer === 'TRUE' ? '正确' : q.answer === 'FALSE' ? '错误' : q.answer
  }
  return q.answer
})
</script>

<template>
  <div class="q-preview">
    <!-- 题干 -->
    <div class="q-content">
      <pre class="q-text">{{ question.content }}</pre>
    </div>

    <!-- 基础信息 -->
    <div class="q-meta">
      <span class="meta-item">
        题型：<b>{{ QUESTION_TYPE_LABELS[question.question_type] || question.question_type }}</b>
      </span>
      <span class="meta-item">
        难度：
        <span :class="['difficulty-badge', `difficulty-badge--${DIFFICULTY_CLASSES[question.difficulty] || ''}`]">
          {{ DIFFICULTY_LABELS[question.difficulty] || question.difficulty }}
        </span>
      </span>
      <span class="meta-item">状态：<QuestionStatusTag :status="question.status" /></span>
    </div>

    <!-- 选项 -->
    <div v-if="isChoiceType(question.question_type) && sortedOptions.length" class="q-section">
      <div class="section-title">选项</div>
      <div class="option-list">
        <div
          v-for="opt in sortedOptions"
          :key="opt.id ?? opt.option_key"
          class="option-item"
          :class="{ correct: opt.is_correct === 1 }"
        >
          <span class="option-key">{{ opt.option_key }}</span>
          <pre class="option-text">{{ opt.option_content }}</pre>
          <span v-if="opt.is_correct === 1" class="correct-mark">正确答案</span>
        </div>
      </div>
    </div>

    <!-- 判断题无选项提示（真实存储：answer=TRUE/FALSE） -->
    <div v-if="question.question_type === 'TRUE_FALSE'" class="q-section">
      <div class="section-title">题型说明</div>
      <div class="plain-note">判断题以「答案」形式存储，无选项。</div>
    </div>

    <!-- 答案 -->
    <div class="q-section">
      <div class="section-title">正确答案</div>
      <pre class="answer-text">{{ answerText }}</pre>
    </div>

    <!-- 解析 -->
    <div class="q-section">
      <div class="section-title">解析</div>
      <pre v-if="question.analysis" class="analysis-text">{{ question.analysis }}</pre>
      <div v-else class="plain-note">暂无解析</div>
    </div>

    <!-- 归属 -->
    <div class="q-section">
      <div class="section-title">归属</div>
      <div class="meta-item">题库：{{ bankName || '#' + question.question_bank_id }}</div>
      <div class="meta-item">
        关联知识点：
        <template v-if="question.knowledge_ids && question.knowledge_ids.length">
          <el-tag v-for="(kid, i) in question.knowledge_ids" :key="kid" size="small" type="info">
            {{ knowledgeNames?.[i] || '#' + kid }}
          </el-tag>
        </template>
        <span v-else>无</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.q-preview {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.q-text {
  margin: 0;
  font-family: inherit;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 16px;
  line-height: 1.7;
  color: var(--color-foreground);
}

.q-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 13px;
  color: var(--color-muted-foreground);
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.q-section {
  border-top: 1px solid var(--color-border);
  padding-top: 12px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-muted-foreground);
  margin-bottom: 8px;
}

.option-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.option-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  background: var(--color-muted);
  border: 1px solid transparent;
}

.option-item.correct {
  background: #ECFDF5;
  border-color: #059669;
}

.option-key {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--color-card);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 13px;
  flex-shrink: 0;
}

.option-text {
  margin: 0;
  flex: 1;
  font-family: inherit;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  line-height: 1.6;
}

.correct-mark {
  font-size: 12px;
  color: #059669;
  font-weight: 600;
  flex-shrink: 0;
}

.answer-text,
.analysis-text {
  margin: 0;
  font-family: inherit;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  line-height: 1.7;
  color: var(--color-foreground);
}

.answer-text {
  font-weight: 600;
}

.plain-note {
  font-size: 13px;
  color: var(--color-muted-foreground);
}
</style>
