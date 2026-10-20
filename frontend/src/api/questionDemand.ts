import request from '@/utils/request'
import type { ApiResponse } from '@/types/auth'
import type {
  KnowledgeImportanceResponse,
  QuestionBankKnowledgeBasesData,
  QuestionBankKnowledgeBasesUpdateRequest,
  QuestionBankKnowledgeBasesUpdateData,
  EffectivePolicyResponse,
  GenerationPolicy,
  AllocationPreviewRequest,
  AllocationPreviewData,
  TaskCreateRequest,
  TaskCreateResponseData,
} from '@/types/questionDemand'

// ==================== 知识点重要程度 ====================

export function updateKnowledgeImportance(
  knowledgeId: number,
  data: { importance_level: string },
): Promise<ApiResponse<KnowledgeImportanceResponse>> {
  return request.patch(`/api/v1/knowledge/${knowledgeId}/importance`, data)
}

// ==================== 题库-知识库映射 ====================
// 注意：GET /knowledge-bases 由 knowledge_base.py 路由优先处理，
// 返回 KnowledgeBaseResponse（status: int, code: string 等），
// 使用已有的 getKnowledgeBaseList（api/knowledgeBase.ts），此处不重复定义。

export function getQuestionBankKnowledgeBases(
  questionBankId: number,
): Promise<ApiResponse<QuestionBankKnowledgeBasesData>> {
  return request.get(`/api/v1/question-banks/${questionBankId}/knowledge-bases`)
}

export function setQuestionBankKnowledgeBases(
  questionBankId: number,
  data: QuestionBankKnowledgeBasesUpdateRequest,
): Promise<ApiResponse<QuestionBankKnowledgeBasesUpdateData>> {
  return request.put(`/api/v1/question-banks/${questionBankId}/knowledge-bases`, data)
}

// ==================== 出题策略 ====================

export function getEffectivePolicy(
  questionBankId?: number | null,
): Promise<ApiResponse<EffectivePolicyResponse>> {
  return request.get('/api/v1/question-generation/policies/effective', {
    params: questionBankId ? { question_bank_id: questionBankId } : {},
  })
}

export function saveGlobalPolicy(
  data: Omit<GenerationPolicy, 'version' | 'updated_at'>,
): Promise<ApiResponse<GenerationPolicy>> {
  return request.put('/api/v1/question-generation/policies/global', data)
}

export function saveQuestionBankPolicy(
  questionBankId: number,
  data: Omit<GenerationPolicy, 'version' | 'updated_at'>,
): Promise<ApiResponse<GenerationPolicy>> {
  return request.put(`/api/v1/question-generation/policies/question-banks/${questionBankId}`, data)
}

export function deleteQuestionBankPolicy(
  questionBankId: number,
): Promise<ApiResponse<null>> {
  return request.delete(`/api/v1/question-generation/policies/question-banks/${questionBankId}`)
}

// ==================== 智能分配预览 ====================

export function previewAllocation(
  data: AllocationPreviewRequest,
): Promise<ApiResponse<AllocationPreviewData>> {
  return request.post('/api/v1/question-generation/allocations/preview', data)
}

// ==================== 任务创建 ====================

export function createGenerationTaskWithAllocation(
  data: TaskCreateRequest,
): Promise<ApiResponse<TaskCreateResponseData>> {
  return request.post('/api/v1/question-generation/tasks', data)
}
