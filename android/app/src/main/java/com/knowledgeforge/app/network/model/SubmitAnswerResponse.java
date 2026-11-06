package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 提交答题结果（对应后端 schema SubmitAnswerResponse，
 * 接口 POST /api/v1/practice/sessions/{session_id}/items/{paper_item_id}/submit 的 data）。
 * 判分结果由服务端按试卷快照内标准答案给出；
 * 同 idempotency_key 重复提交返回原记录且 idempotent=true。
 */
public class SubmitAnswerResponse {

    /** 答题记录 ID。 */
    @SerializedName("answer_record_id")
    private int answerRecordId;

    /** 是否幂等复用（true=命中 idempotency_key 缓存，返回原答题记录）。 */
    @SerializedName("idempotent")
    private boolean idempotent;

    /** 对应试卷题目项 ID。 */
    @SerializedName("paper_item_id")
    private int paperItemId;

    /** 题目 ID（可空）。 */
    @SerializedName("question_id")
    private Integer questionId;

    /** 判分结果（true=对 false=错 null=未判分）。 */
    @SerializedName("is_correct")
    private Boolean isCorrect;

    /** 判分状态（graded|ungraded）。 */
    @SerializedName("grading_status")
    private String gradingStatus;

    /** 本题得分（可空，未判分或未给出时为 null）。 */
    @SerializedName("score")
    private Double score;

    /** 标准答案（可空，判分后回显）。 */
    @SerializedName("correct_answer")
    private String correctAnswer;

    /** 答案解析（可空）。 */
    @SerializedName("explanation")
    private String explanation;

    /** 提交后的会话进度摘要（用于实时刷新界面统计）。 */
    @SerializedName("session_progress")
    private SessionProgressInfo sessionProgress;

    public int getAnswerRecordId() {
        return answerRecordId;
    }

    public boolean isIdempotent() {
        return idempotent;
    }

    public int getPaperItemId() {
        return paperItemId;
    }

    public Integer getQuestionId() {
        return questionId;
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

    public String getCorrectAnswer() {
        return correctAnswer;
    }

    public String getExplanation() {
        return explanation;
    }

    public SessionProgressInfo getSessionProgress() {
        return sessionProgress;
    }
}
