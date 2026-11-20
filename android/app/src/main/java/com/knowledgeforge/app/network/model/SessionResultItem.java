package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 整卷结果题目项（对应后端 schema SessionResultItem；
 * 后端继承链为 QuestionResultItem(QuestionSnapshotItem) + status，此处合并为一层继承 QuestionSnapshotItem），
 * 接口 GET /api/v1/practice/sessions/{session_id}/result 的 items[] 元素。
 * 答案安全投影：in_progress/abandoned 会话的未提交题目不返回
 * correct_answer/explanation/is_correct（缺省为 null，仅已提交题返回自身判分结果），
 * completed 会话全量返回正确答案与解析。
 */
public class SessionResultItem extends QuestionSnapshotItem {

    /** 标准答案（仅已提交题返回；单选如 "A"，多选如 "A,C"，判断如 "true"）。 */
    @SerializedName("correct_answer")
    private String correctAnswer;

    /** 答案解析（仅已提交题返回，可空）。 */
    @SerializedName("explanation")
    private String explanation;

    /**
     * 我的答案（仅已提交题返回，多态，按题型）：
     * 单选=选项键字符串、多选=选项键数组、判断=布尔、简答=文本。
     */
    @SerializedName("your_answer")
    private Object yourAnswer;

    /** 判分结果（仅已提交题返回：true=对 false=错 null=未判分）。 */
    @SerializedName("is_correct")
    private Boolean isCorrect;

    /** 判分状态（仅已提交题返回：graded|ungraded）。 */
    @SerializedName("grading_status")
    private String gradingStatus;

    /** 首次提交时间（ISO 8601 字符串，未提交为 null）。 */
    @SerializedName("first_submitted_at")
    private String firstSubmittedAt;

    /** 最近提交时间（ISO 8601 字符串，未提交为 null）。 */
    @SerializedName("last_submitted_at")
    private String lastSubmittedAt;

    /** 题目项状态：unanswered=未作答，draft_saved=有草稿，answered=已提交。 */
    @SerializedName("status")
    private String status;

    public String getCorrectAnswer() {
        return correctAnswer;
    }

    public String getExplanation() {
        return explanation;
    }

    public Object getYourAnswer() {
        return yourAnswer;
    }

    public Boolean getIsCorrect() {
        return isCorrect;
    }

    public String getGradingStatus() {
        return gradingStatus;
    }

    public String getFirstSubmittedAt() {
        return firstSubmittedAt;
    }

    public String getLastSubmittedAt() {
        return lastSubmittedAt;
    }

    public String getStatus() {
        return status;
    }
}
