package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

import java.util.List;
import java.util.Map;

/**
 * 组卷请求体（对应后端 schema AssemblePaperRequest，
 * 接口 POST /api/v1/practice/papers/assemble）。
 * 按题型/难度分布从开放练习题库抽取已发布题目，生成不可变快照试卷，
 * 并自动创建首个练习会话。校验失败或 allow_partial=false 且库存不足时零落库。
 * 幂等：可另传请求头 Idempotency-Key（见接口声明），同 key 同参返回原卷。
 */
public class AssemblePaperRequest {

    /** 题库 ID（必填）；必须为已开放练习（is_available_for_practice=true）的题库。 */
    @SerializedName("question_bank_id")
    private int questionBankId;

    /** 试卷标题（可选；未传时后端按项目约定生成默认标题）。 */
    @SerializedName("title")
    private String title;

    /** 限定知识点 ID 列表（可选）；每个 ID 必须与指定题库存在真实关联，无效 ID 直接参数错误 40001。 */
    @SerializedName("knowledge_ids")
    private List<Integer> knowledgeIds;

    /**
     * 题型数量分布（可选），键限 SINGLE_CHOICE/MULTIPLE_CHOICE/TRUE_FALSE/SHORT_ANSWER，
     * 例如 {"SINGLE_CHOICE": 3, "TRUE_FALSE": 2}；
     * 与 difficulty_distribution 各项之和须等于 total_count。
     */
    @SerializedName("question_type_counts")
    private Map<String, Integer> questionTypeCounts;

    /** 难度分布（可选）{easy: 2, normal: 2, hard: 1}。 */
    @SerializedName("difficulty_distribution")
    private DifficultyDistribution difficultyDistribution;

    /** 题目数量（必填），必须与题型分布、难度分布之和一致。 */
    @SerializedName("total_count")
    private int totalCount;

    /** 库存不足时是否允许按可用量出卷（可选，默认不允许，不静默少题）。 */
    @SerializedName("allow_partial")
    private Boolean allowPartial;

    /** 抽题策略（可选，目前后端仅支持 random）。 */
    @SerializedName("selection_strategy")
    private String selectionStrategy;

    public AssemblePaperRequest(int questionBankId, int totalCount) {
        this.questionBankId = questionBankId;
        this.totalCount = totalCount;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public void setKnowledgeIds(List<Integer> knowledgeIds) {
        this.knowledgeIds = knowledgeIds;
    }

    public void setQuestionTypeCounts(Map<String, Integer> questionTypeCounts) {
        this.questionTypeCounts = questionTypeCounts;
    }

    public void setDifficultyDistribution(DifficultyDistribution difficultyDistribution) {
        this.difficultyDistribution = difficultyDistribution;
    }

    public void setAllowPartial(Boolean allowPartial) {
        this.allowPartial = allowPartial;
    }

    public void setSelectionStrategy(String selectionStrategy) {
        this.selectionStrategy = selectionStrategy;
    }

    public int getQuestionBankId() {
        return questionBankId;
    }

    public String getTitle() {
        return title;
    }

    public List<Integer> getKnowledgeIds() {
        return knowledgeIds;
    }

    public Map<String, Integer> getQuestionTypeCounts() {
        return questionTypeCounts;
    }

    public DifficultyDistribution getDifficultyDistribution() {
        return difficultyDistribution;
    }

    public int getTotalCount() {
        return totalCount;
    }

    public Boolean getAllowPartial() {
        return allowPartial;
    }

    public String getSelectionStrategy() {
        return selectionStrategy;
    }
}
