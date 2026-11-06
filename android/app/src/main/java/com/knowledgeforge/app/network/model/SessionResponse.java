package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 练习会话（对应后端 schema SessionResponse，练习会话主记录）。
 * 是组卷响应 AssemblePaperResponse.session、会话详情 SessionDetailResponse.session、
 * resume/complete 响应以及会话列表条目 SessionListItem 的基础形状。
 * 记录一张试卷上的一次练习进程与各状态题数统计。
 */
public class SessionResponse {

    /** 练习会话 ID。 */
    @SerializedName("session_id")
    private int sessionId;

    /** 所属试卷 ID（practice_paper）。 */
    @SerializedName("paper_id")
    private int paperId;

    /** 练习模式（当前固定 practice）。 */
    @SerializedName("mode")
    private String mode;

    /** 会话状态：in_progress|completed|abandoned。 */
    @SerializedName("status")
    private String status;

    /** 当前题序（1~total_count，配合进度更新接口使用）。 */
    @SerializedName("current_item_order")
    private int currentItemOrder;

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

    /** 未判分题数（如简答题待批改）。 */
    @SerializedName("ungraded_count")
    private int ungradedCount;

    /** 开始时间（ISO 8601 字符串，可空）。 */
    @SerializedName("started_at")
    private String startedAt;

    /** 最后活跃时间（ISO 8601 字符串，可空）。 */
    @SerializedName("last_active_at")
    private String lastActiveAt;

    /** 完成时间（ISO 8601 字符串，未完成为 null）。 */
    @SerializedName("completed_at")
    private String completedAt;

    /** 放弃时间（ISO 8601 字符串，未放弃为 null）。 */
    @SerializedName("abandoned_at")
    private String abandonedAt;

    /** 练习累计时长（毫秒，可空）。 */
    @SerializedName("duration_ms")
    private Long durationMs;

    public int getSessionId() {
        return sessionId;
    }

    public int getPaperId() {
        return paperId;
    }

    public String getMode() {
        return mode;
    }

    public String getStatus() {
        return status;
    }

    public int getCurrentItemOrder() {
        return currentItemOrder;
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

    public String getStartedAt() {
        return startedAt;
    }

    public String getLastActiveAt() {
        return lastActiveAt;
    }

    public String getCompletedAt() {
        return completedAt;
    }

    public String getAbandonedAt() {
        return abandonedAt;
    }

    public Long getDurationMs() {
        return durationMs;
    }
}
