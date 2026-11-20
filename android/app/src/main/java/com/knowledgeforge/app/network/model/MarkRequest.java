package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 标记/取消标记题目请求体（对应后端 schema MarkRequest，
 * 接口 PATCH /api/v1/practice/sessions/{session_id}/items/{paper_item_id}/mark）。
 * 标记状态与作答状态相互独立，幂等（重复置同一值不报错）。
 */
public class MarkRequest {

    /** 标记状态（必填）：true=标记为疑难题，false=取消标记。 */
    @SerializedName("is_marked")
    private boolean isMarked;

    /**
     * 构造器：设置标记状态。
     *
     * @param isMarked true=标记为疑难题，false=取消标记
     */
    public MarkRequest(boolean isMarked) {
        this.isMarked = isMarked;
    }

    public boolean isMarked() {
        return isMarked;
    }
}
