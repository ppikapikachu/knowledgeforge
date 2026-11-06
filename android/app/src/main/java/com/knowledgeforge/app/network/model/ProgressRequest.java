package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 更新练习进度请求体（对应后端 schema ProgressRequest，
 * 接口 PATCH /api/v1/practice/sessions/{session_id}/progress）。
 * 只记录用户当前做到第几题，便于恢复练习位置；不改变答题状态与统计。
 */
public class ProgressRequest {

    /** 当前题序（必填，1~试卷题量 total_count，越界报业务错误 40001）。 */
    @SerializedName("current_item_order")
    private int currentItemOrder;

    public ProgressRequest(int currentItemOrder) {
        this.currentItemOrder = currentItemOrder;
    }

    public int getCurrentItemOrder() {
        return currentItemOrder;
    }
}
