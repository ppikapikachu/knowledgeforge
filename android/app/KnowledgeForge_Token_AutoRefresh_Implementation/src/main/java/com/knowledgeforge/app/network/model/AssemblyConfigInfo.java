package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

import java.util.List;
import java.util.Map;

/**
 * 组卷参数快照（对应后端 schema AssemblyConfigInfo，
 * 出现在 PaperResponse.assembly_config 字段）。
 * 记录生成该试卷时的抽题参数；历史行可能缺键，故所有字段均可缺省（用包装类型）。
 */
public class AssemblyConfigInfo {

    /** 组卷来源题库 ID（可空）。 */
    @SerializedName("question_bank_id")
    private Integer questionBankId;

    /** 组卷限定的知识点 ID 列表（升序去重；未限定知识点为空列表）。 */
    @SerializedName("knowledge_ids")
    private List<Integer> knowledgeIds;

    /**
     * 题型数量分布：键=题型（SINGLE_CHOICE/MULTIPLE_CHOICE/TRUE_FALSE/SHORT_ANSWER），值=题量。
     */
    @SerializedName("question_type_counts")
    private Map<String, Integer> questionTypeCounts;

    /** 难度分布（easy/normal/hard 各难度题量）。 */
    @SerializedName("difficulty_distribution")
    private DifficultyDistribution difficultyDistribution;

    /** 组卷题目总数（可空）。 */
    @SerializedName("total_count")
    private Integer totalCount;

    /** 抽题策略（当前固定 random，可空）。 */
    @SerializedName("selection_strategy")
    private String selectionStrategy;

    public Integer getQuestionBankId() {
        return questionBankId;
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

    public Integer getTotalCount() {
        return totalCount;
    }

    public String getSelectionStrategy() {
        return selectionStrategy;
    }
}
