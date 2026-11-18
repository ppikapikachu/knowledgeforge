package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 个人中心统计（对应后端 schema UserStatisticsResponse，
 * 接口 GET /api/v1/users/me/statistics 的 data）。
 * 答题表现与练习表现分开呈现；正确率样本不足时不给具体数值。
 */
public class UserStatisticsResponse {

    /** 答题表现摘要。 */
    @SerializedName("answer_summary")
    private UserAnswerSummary answerSummary;

    /** 练习表现摘要。 */
    @SerializedName("practice_summary")
    private UserPracticeSummary practiceSummary;

    public UserAnswerSummary getAnswerSummary() {
        return answerSummary;
    }

    public UserPracticeSummary getPracticeSummary() {
        return practiceSummary;
    }
}
