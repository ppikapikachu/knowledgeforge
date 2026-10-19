/**
 * 题库管理模块共用的下拉数据源与 ID→名称 映射。
 * 数据全部来自真实接口（question-banks / knowledge 列表）。
 */
import { ref, computed } from 'vue'
import { getQuestionBankList } from '@/api/questionBank'
import { getKnowledgeList } from '@/api/knowledge'
import type { QuestionBank } from '@/types/questionManagement'
import type { Knowledge } from '@/types/knowledge'

export function useQuestionLookups() {
  const banks = ref<QuestionBank[]>([])
  const knowledgeList = ref<Knowledge[]>([])
  const loading = ref(false)
  const knowledgeLoading = ref(false)

  async function loadAll() {
    loading.value = true
    try {
      const [bankRes, kbRes] = await Promise.all([
        getQuestionBankList({ page: 1, page_size: 100 }),
        getKnowledgeList({ page: 1, page_size: 100 }),
      ])
      banks.value = bankRes.data.items
      knowledgeList.value = kbRes.data.items
    } finally {
      loading.value = false
    }
  }

  const bankNameMap = computed(() => {
    const map = new Map<number, string>()
    for (const b of banks.value) map.set(b.id, b.name)
    return map
  })

  const knowledgeNameMap = computed(() => {
    const map = new Map<number, string>()
    for (const k of knowledgeList.value) map.set(k.id, k.name)
    return map
  })

  function bankName(id: number): string {
    return bankNameMap.value.get(id) || `#${id}`
  }

  function knowledgeName(id: number): string {
    return knowledgeNameMap.value.get(id) || `#${id}`
  }

  /** 知识点远程搜索（供下拉使用） */
  async function searchKnowledge(keyword: string): Promise<Knowledge[]> {
    const res = await getKnowledgeList({ keyword: keyword || undefined, page: 1, page_size: 20 })
    return res.data.items
  }

  return {
    banks,
    knowledgeList,
    loading,
    loadAll,
    bankName,
    knowledgeName,
    searchKnowledge,
    knowledgeLoading,
  }
}
