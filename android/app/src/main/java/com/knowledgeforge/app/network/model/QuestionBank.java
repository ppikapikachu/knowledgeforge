package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

import java.util.Map;

/**
 * 开放练习题库（对应后端 schema OpenQuestionBankItem / OpenQuestionBankResponse，
 * 接口 GET /api/v1/practice/question-banks 列表项）。
 * 只包含普通用户可见的练习题库（is_available_for_practice=true 的题库）；
 * 空库存题库也返回（can_assemble=false 并给出 unavailable_reason）。
 */
public class QuestionBank {

    /** 题库 ID。 */
    @SerializedName("id")
    private int id;

    /** 题库编码。 */
    @SerializedName("code")
    private String code;

    /** 题库名称。 */
    @SerializedName("name")
    private String name;

    /** 题库描述。 */
    @SerializedName("description")
    private String description;

    /**
     * 是否开放练习（文档说明此处恒 true；当前后端实现的响应体未包含该字段，
     * 反序列化结果可能为 null）。
     */
    @SerializedName("is_available_for_practice")
    private Boolean isAvailableForPractice;

    /** 可练习题量（已发布 published 题数）。 */
    @SerializedName("available_question_count")
    private int availableQuestionCount;

    /**
     * 各题型可练习题量，键为题型
     * （SINGLE_CHOICE/MULTIPLE_CHOICE/TRUE_FALSE/SHORT_ANSWER），值为题量。
     */
    @SerializedName("question_type_counts")
    private Map<String, Integer> questionTypeCounts;

    /** 各难度可练习题量（键 easy/normal/hard，值为题量）。 */
    @SerializedName("difficulty_counts")
    private Map<String, Integer> difficultyCounts;

    /** 是否可组卷（有可练习题时为 true）。 */
    @SerializedName("can_assemble")
    private boolean canAssemble;

    /** 不可组卷原因（可组卷时为 null；空库存时为「暂无可练习题目」）。 */
    @SerializedName("unavailable_reason")
    private String unavailableReason;

    public int getId() {
        return id;
    }

    public String getCode() {
        return code;
    }

    public String getName() {
        return name;
    }

    public String getDescription() {
        return description;
    }

    public Boolean getIsAvailableForPractice() {
        return isAvailableForPractice;
    }

    public int getAvailableQuestionCount() {
        return availableQuestionCount;
    }

    public Map<String, Integer> getQuestionTypeCounts() {
        return questionTypeCounts;
    }

    public Map<String, Integer> getDifficultyCounts() {
        return difficultyCounts;
    }

    public boolean isCanAssemble() {
        return canAssemble;
    }

    public String getUnavailableReason() {
        return unavailableReason;
    }
}
