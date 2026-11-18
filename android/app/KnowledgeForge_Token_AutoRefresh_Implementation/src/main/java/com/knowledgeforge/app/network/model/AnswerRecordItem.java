package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 答题历史条目（对应后端 schema app.schemas.answer.AnswerRecordItem，
 * 接口 GET /api/v1/answers/history 分页信封的 items[] 元素）。
 * 注意 is_correct 用 Integer 表示三态：1=正确 / 0=错误 / null=未判分。
 * 练习内答题才有 practice_* 关联字段，自由刷题为空。
 */
public class AnswerRecordItem {

    /** 答题记录 ID。 */
    @SerializedName("id")
    private int id;

    /** 题目 ID。 */
    @SerializedName("question_id")
    private int questionId;

    /** 用户提交答案（字符串形态：单选 "A"、多选 "A,C"、判断 "true"/"false"、简答文本；可空）。 */
    @SerializedName("user_answer")
    private String userAnswer;

    /** 判分结果：1=正确 / 0=错误 / null=未判分（注意不是 Boolean）。 */
    @SerializedName("is_correct")
    private Integer isCorrect;

    /** 判分状态（如 graded|ungraded）。 */
    @SerializedName("grading_status")
    private String gradingStatus;

    /** 本题得分（可空）。 */
    @SerializedName("score")
    private Double score;

    /** 本题作答耗时（毫秒，可空）。 */
    @SerializedName("time_spent_ms")
    private Long timeSpentMs;

    /** 关联练习试卷 ID（自由刷题为空）。 */
    @SerializedName("practice_paper_id")
    private Integer practicePaperId;

    /** 关联试卷题目项 ID（自由刷题为空）。 */
    @SerializedName("practice_paper_item_id")
    private Integer practicePaperItemId;

    /** 关联练习会话 ID（自由刷题为空）。 */
    @SerializedName("practice_session_id")
    private Integer practiceSessionId;

    /** 幂等键（可空）。 */
    @SerializedName("idempotency_key")
    private String idempotencyKey;

    /** 提交时间（ISO 8601 字符串，可空）。 */
    @SerializedName("created_at")
    private String createdAt;

    public int getId() {
        return id;
    }

    public int getQuestionId() {
        return questionId;
    }

    public String getUserAnswer() {
        return userAnswer;
    }

    public Integer getIsCorrect() {
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

    public Integer getPracticePaperId() {
        return practicePaperId;
    }

    public Integer getPracticePaperItemId() {
        return practicePaperItemId;
    }

    public Integer getPracticeSessionId() {
        return practiceSessionId;
    }

    public String getIdempotencyKey() {
        return idempotencyKey;
    }

    public String getCreatedAt() {
        return createdAt;
    }
}
