package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 最近一次练习会话摘要（对应后端 schema RecentSessionInfo，
 * 出现在试卷列表 PaperListItem.recent_session 字段）。
 * 该试卷从未练习过时为 null。
 */
public class RecentSessionInfo {

    /** 练习会话 ID。 */
    @SerializedName("session_id")
    private int sessionId;

    /** 会话状态：in_progress|completed|abandoned。 */
    @SerializedName("status")
    private String status;

    /** 已作答题数。 */
    @SerializedName("answered_count")
    private int answeredCount;

    /** 题目总数。 */
    @SerializedName("total_count")
    private int totalCount;

    /** 最后活跃时间（ISO 8601 字符串，可空）。 */
    @SerializedName("last_active_at")
    private String lastActiveAt;

    public int getSessionId() {
        return sessionId;
    }

    public String getStatus() {
        return status;
    }

    public int getAnsweredCount() {
        return answeredCount;
    }

    public int getTotalCount() {
        return totalCount;
    }

    public String getLastActiveAt() {
        return lastActiveAt;
    }
}
