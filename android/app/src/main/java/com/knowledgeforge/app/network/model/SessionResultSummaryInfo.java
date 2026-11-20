package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 整卷结果汇总（对应后端 schema SessionResultSummaryInfo，
 * 接口 GET /api/v1/practice/sessions/{session_id}/result 的 summary 字段）。
 * 与会话统计口径一致：correct/incorrect/ungraded 按已判分记录统计。
 */
public class SessionResultSummaryInfo {

    /** 题目总数。 */
    @SerializedName("total_count")
    private int totalCount;

    /** 已作答题数。 */
    @SerializedName("answered_count")
    private int answeredCount;

    /** 判分正确题数。 */
    @SerializedName("correct_count")
    private int correctCount;

    /** 判分错误题数。 */
    @SerializedName("incorrect_count")
    private int incorrectCount;

    /** 未判分题数（如简答题）。 */
    @SerializedName("ungraded_count")
    private int ungradedCount;

    /** 试卷总分。 */
    @SerializedName("total_score")
    private double totalScore;

    /** 累计得分。 */
    @SerializedName("earned_score")
    private double earnedScore;

    public int getTotalCount() {
        return totalCount;
    }

    public int getAnsweredCount() {
        return answeredCount;
    }

    public int getCorrectCount() {
        return correctCount;
    }

    public int getIncorrectCount() {
        return incorrectCount;
    }

    public int getUngradedCount() {
        return ungradedCount;
    }

    public double getTotalScore() {
        return totalScore;
    }

    public double getEarnedScore() {
        return earnedScore;
    }
}
