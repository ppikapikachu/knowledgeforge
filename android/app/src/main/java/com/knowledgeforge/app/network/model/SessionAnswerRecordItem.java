package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 会话答题记录条目（对应后端 schema practice.AnswerRecordItem，
 * 接口 GET /api/v1/practice/sessions/{session_id}/answers 的 answers[] 元素）。
 * 注意与 {@link AnswerRecordItem}（answers/history 用的 answer 模块变体）区分：
 * 本类 is_correct 为布尔三态（true/false/null=未评分），且固定属于练习会话
 * （practice_paper_item_id 必有，无自由刷题场景的可空外键）。
 * 每次提交追加一条记录，同 idempotency_key 重复提交不追加。
 */
public class SessionAnswerRecordItem {

    /** 答题记录 ID。 */
    @SerializedName("id")
    private int id;

    /** 源题目 ID（快照无源题时可能为 null）。 */
    @SerializedName("question_id")
    private Integer questionId;

    /** 试卷题目项 ID（practice_paper_item 主键）。 */
    @SerializedName("practice_paper_item_id")
    private int practicePaperItemId;

    /** 用户作答文本（规范化后的文本表示）。 */
    @SerializedName("user_answer")
    private String userAnswer;

    /** 是否判分正确（true=对 false=错 null=未评分简答题）。 */
    @SerializedName("is_correct")
    private Boolean isCorrect;

    /** 判分状态：graded|ungraded。 */
    @SerializedName("grading_status")
    private String gradingStatus;

    /** 本题得分（未评分为 null）。 */
    @SerializedName("score")
    private Double score;

    /** 作答耗时（毫秒，可空）。 */
    @SerializedName("time_spent_ms")
    private Long timeSpentMs;

    /** 提交幂等键（8~64 位；历史/兼容记录可能为 null）。 */
    @SerializedName("idempotency_key")
    private String idempotencyKey;

    /** 提交时间（ISO 8601 字符串）。 */
    @SerializedName("created_at")
    private String createdAt;

    public int getId() {
        return id;
    }

    public Integer getQuestionId() {
        return questionId;
    }

    public int getPracticePaperItemId() {
        return practicePaperItemId;
    }

    public String getUserAnswer() {
        return userAnswer;
    }

    public Boolean getIsCorrect() {
        return isCorrect;
    }

    public String getGradingStatus() {
        return gradingStatus;
    }

    public Double getScore() {
        return score;
    }

    public Long getTimeSpentMs() {
        return timeSpentMs;
    }

    public String getIdempotencyKey() {
        return idempotencyKey;
    }

    public String getCreatedAt() {
        return createdAt;
    }
}
