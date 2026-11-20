package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

import java.util.List;

/**
 * 试卷详情（对应后端 schema PaperDetailResponse，
 * 接口 GET /api/v1/practice/papers/{paper_id}）。
 * 字段 = 试卷快照头（继承 PaperResponse） + 题目面投影 items[]。
 * 注意：items 元素不含正确答案/解析（白名单投影），与会话详情/结果接口区分。
 */
public class PaperDetailResponse extends PaperResponse {

    /** 题目面投影列表（按试卷题序，不含正确答案与解析）。 */
    @SerializedName("items")
    private List<QuestionSnapshotItem> items;

    public List<QuestionSnapshotItem> getItems() {
        return items;
    }
}
