package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 草稿内容包装（对应后端 schema DraftAnswerInfo，形如 {"answer": 作答值}），
 * 用于 DraftSaveResponse.draft_answer，回显保存后的最新草稿。
 */
public class DraftAnswerInfo {

    /**
     * 草稿答案（多态，按题型）：
     * 单选/简答=字符串、多选=选项键数组、判断=布尔（兼容字符串）。
     */
    @SerializedName("answer")
    private Object answer;

    public Object getAnswer() {
        return answer;
    }
}
