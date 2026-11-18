package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 练习进度更新结果（对应后端 schema ProgressUpdateResponse，
 * 接口 PATCH /api/v1/practice/sessions/{session_id}/progress 的 data）。
 * 仅记录用户当前做到第几题，不改变答题状态与统计。
 */
public class ProgressUpdateResponse {

    /** 练习会话 ID。 */
    @SerializedName("session_id")
    private int sessionId;

    /** 更新后的当前题序。 */
    @SerializedName("current_item_order")
    private int currentItemOrder;

    public int getSessionId() {
        return sessionId;
    }

    public int getCurrentItemOrder() {
        return currentItemOrder;
    }
}
