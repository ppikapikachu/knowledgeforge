package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 我的试卷列表条目（对应后端 schema PaperListItem，
 * 接口 GET /api/v1/practice/papers 分页信封的 items[] 元素）。
 * 字段 = 试卷快照头（继承 PaperResponse） + 最近一次练习会话摘要 recent_session。
 */
public class PaperListItem extends PaperResponse {

    /** 最近一次练习会话摘要（从未练习为 null）。 */
    @SerializedName("recent_session")
    private RecentSessionInfo recentSession;

    public RecentSessionInfo getRecentSession() {
        return recentSession;
    }
}
