package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 答题表现摘要（对应后端 schema UserAnswerSummary，
 * 见于个人中心统计 UserStatisticsResponse.answer_summary）。
 * 正确率在样本不足时不给具体数值，由 display_status 说明原因。
 */
public class UserAnswerSummary {

    /** 已判分提交次数（被替换的旧版本答案也计入）。 */
    @SerializedName("graded_submission_count")
    private int gradedSubmissionCount;

    /** 已判分答对次数。 */
    @SerializedName("correct_submission_count")
    private int correctSubmissionCount;

    /** 总正确率（0.0000~1.0000；样本不足为 null）。 */
    @SerializedName("accuracy")
    private Double accuracy;

    /** 首次作答正确率（每题只取第一次提交；样本不足为 null）。 */
    @SerializedName("first_attempt_accuracy")
    private Double firstAttemptAccuracy;

    /** 至少作答过一次的题数。 */
    @SerializedName("answered_question_count")
    private int answeredQuestionCount;

    /** 正确率展示状态：available=可展示|insufficient_samples=样本不足。 */
    @SerializedName("display_status")
    private String displayStatus;

    /** 正确率展示所需最少判分次数（当前默认 20）。 */
    @SerializedName("sample_threshold")
    private int sampleThreshold;

    public int getGradedSubmissionCount() {
        return gradedSubmissionCount;
    }

    public int getCorrectSubmissionCount() {
        return correctSubmissionCount;
    }

    public Double getAccuracy() {
        return accuracy;
    }

    public Double getFirstAttemptAccuracy() {
        return firstAttemptAccuracy;
    }

    public int getAnsweredQuestionCount() {
        return answeredQuestionCount;
    }

    public String getDisplayStatus() {
        return displayStatus;
    }

    public int getSampleThreshold() {
        return sampleThreshold;
    }
}
