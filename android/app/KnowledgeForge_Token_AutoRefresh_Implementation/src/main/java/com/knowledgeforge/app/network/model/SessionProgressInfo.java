package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 会话进度摘要（对应后端 schema SessionProgressInfo）。
 * 随提交答题响应 SubmitAnswerResponse.session_progress 与
 * 会话详情 SessionDetailResponse.progress 返回，供界面实时刷新进度与统计。
 */
public class SessionProgressInfo {

    /** 练习会话 ID。 */
    @SerializedName("session_id")
    private int sessionId;

    /** 会话状态：in_progress|completed|abandoned。 */
    @SerializedName("status")
    private String status;

    /** 题目总数。 */
    @SerializedName("total_count")
    private int totalCount;

    /** 已作答题数。 */
    @SerializedName("answered_count")
    private int answeredCount;

    /** 已判分答对题数。 */
    @SerializedName("correct_count")
    private int correctCount;

    /** 已判分答错题数。 */
    @SerializedName("incorrect_count")
    private int incorrectCount;

    /** 未判分题数。 */
    @SerializedName("ungraded_count")
    private int ungradedCount;

    /** 当前题序。 */
    @SerializedName("current_item_order")
    private int currentItemOrder;

    public int getSessionId() {
        return sessionId;
    }

    public String getStatus() {
        return status;
    }

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

    public int getCurrentItemOrder() {
        return currentItemOrder;
    }
}
