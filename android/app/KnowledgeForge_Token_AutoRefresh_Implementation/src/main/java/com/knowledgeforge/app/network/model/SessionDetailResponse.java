package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

import java.util.List;

/**
 * 会话详情（对应后端 schema SessionDetailResponse，
 * 接口 GET /api/v1/practice/sessions/{session_id} 的 data）。
 * 一次返回恢复练习所需的全部内容：会话、试卷快照头、全部题目项、进度摘要。
 */
public class SessionDetailResponse {

    /** 练习会话主记录。 */
    @SerializedName("session")
    private SessionResponse session;

    /** 所属试卷快照头。 */
    @SerializedName("paper")
    private PaperResponse paper;

    /** 题目项列表（按试卷题序；仅返回答案安全投影，未作答题不含正确答案）。 */
    @SerializedName("items")
    private List<SessionDetailItem> items;

    /** 进度摘要。 */
    @SerializedName("progress")
    private SessionProgressInfo progress;

    public SessionResponse getSession() {
        return session;
    }

    public PaperResponse getPaper() {
        return paper;
    }

    public List<SessionDetailItem> getItems() {
        return items;
    }

    public SessionProgressInfo getProgress() {
        return progress;
    }
}
