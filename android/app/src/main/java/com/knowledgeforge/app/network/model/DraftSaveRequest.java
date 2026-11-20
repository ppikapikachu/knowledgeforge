package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 保存题目草稿请求体（对应后端 schema DraftSaveRequest，
 * 接口 PUT /api/v1/practice/sessions/{session_id}/items/{paper_item_id}/draft）。
 * 仅写草稿不判分、不进统计；同一题目项反复保存幂等覆盖，仅保留最新草稿；
 * completed/abandoned 会话保存草稿报 40001。
 */
public class DraftSaveRequest {

    /**
     * 草稿答案（多态，按题型）：
     * 单选/简答=选项键或文本字符串、多选=选项键数组、判断=布尔（兼容字符串）。
     * 后端 schema 中可缺省（default null）。
     */
    @SerializedName("answer")
    private Object answer;

    /**
     * 构造器：直传草稿内容。
     *
     * @param answer 草稿答案（多态，见字段说明；传 null 表示清空草稿）
     */
    public DraftSaveRequest(Object answer) {
        this.answer = answer;
    }

    /**
     * 设置草稿内容（answer 在后端 schema 中可缺省，故也提供 setter）。
     *
     * @param answer 草稿答案（多态，见字段说明）
     */
    public void setAnswer(Object answer) {
        this.answer = answer;
    }

    public Object getAnswer() {
        return answer;
    }
}
