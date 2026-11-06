package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 练习表现摘要（对应后端 schema UserPracticeSummary，
 * 见于个人中心统计 UserStatisticsResponse.practice_summary）。
 */
public class UserPracticeSummary {

    /** 总会话数。 */
    @SerializedName("session_total")
    private int sessionTotal;

    /** 已完成会话数。 */
    @SerializedName("session_completed")
    private int sessionCompleted;

    /** 进行中会话数。 */
    @SerializedName("session_in_progress")
    private int sessionInProgress;

    /** 已放弃会话数。 */
    @SerializedName("session_abandoned")
    private int sessionAbandoned;

    /** 练习累计时长（毫秒）。 */
    @SerializedName("total_duration_ms")
    private long totalDurationMs;

    public int getSessionTotal() {
        return sessionTotal;
    }

    public int getSessionCompleted() {
        return sessionCompleted;
    }

    public int getSessionInProgress() {
        return sessionInProgress;
    }

    public int getSessionAbandoned() {
        return sessionAbandoned;
    }

    public long getTotalDurationMs() {
        return totalDurationMs;
    }
}
