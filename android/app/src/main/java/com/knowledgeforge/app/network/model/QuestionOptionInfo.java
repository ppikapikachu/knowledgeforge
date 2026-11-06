package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 题目选项（对应后端 schema QuestionOptionInfo，见于会话详情题目项 SessionDetailItem.options）。
 * 仅在选择题（单选/多选）中出现，判断题/简答题为空列表。
 */
public class QuestionOptionInfo {

    /** 选项键（如 "A"/"B"；判断题为 true/false 键，可空）。 */
    @SerializedName("option_key")
    private String optionKey;

    /** 选项内容（可空）。 */
    @SerializedName("content")
    private String content;

    public String getOptionKey() {
        return optionKey;
    }

    public String getContent() {
        return content;
    }
}
