package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 保存题目草稿响应（对应后端 schema DraftSaveResponse，
 * 接口 PUT /api/v1/practice/sessions/{session_id}/items/{paper_item_id}/draft）。
 * 回显草稿保存后的题目项状态与最新草稿内容。
 */
public class DraftSaveResponse {

    /** 练习会话 ID。 */
    @SerializedName("session_id")
    private int sessionId;

    /** 试卷题目项 ID。 */
    @SerializedName("paper_item_id")
    private int paperItemId;

    /** 题目项状态（draft_saved=草稿已保存；若该题已提交过则保持 answered 不回退）。 */
    @SerializedName("status")
    private String status;

    /** 最新草稿内容（{answer: 作答值} 包装对象）。 */
    @SerializedName("draft_answer")
    private DraftAnswerInfo draftAnswer;

    public int getSessionId() {
        return sessionId;
    }

    public int getPaperItemId() {
        return paperItemId;
    }

    public String getStatus() {
        return status;
    }

    public DraftAnswerInfo getDraftAnswer() {
        return draftAnswer;
    }
}
