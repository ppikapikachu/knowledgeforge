package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 标记/取消标记题目响应（对应后端 schema MarkItemResponse，
 * 接口 PATCH /api/v1/practice/sessions/{session_id}/items/{paper_item_id}/mark）。
 * 回显题目项最新标记状态。
 */
public class MarkItemResponse {

    /** 试卷题目项 ID。 */
    @SerializedName("paper_item_id")
    private int paperItemId;

    /** 当前标记状态：true=已标记为疑难题，false=未标记。 */
    @SerializedName("is_marked")
    private boolean isMarked;

    public int getPaperItemId() {
        return paperItemId;
    }

    public boolean isMarked() {
        return isMarked;
    }
}
