package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

import java.util.List;

/**
 * 整卷结果与解析（对应后端 schema SessionResultResponse，
 * 接口 GET /api/v1/practice/sessions/{session_id}/result）。
 * 一次返回会话信息 + 全部题目结果投影 + 结果汇总，供练习结束/回顾页使用；
 * 答案安全投影规则同 SessionResultItem（未提交题不泄露正确答案）。
 */
public class SessionResultResponse {

    /** 会话信息。 */
    @SerializedName("session")
    private SessionResponse session;

    /** 题目结果投影列表（按试卷题序）。 */
    @SerializedName("items")
    private List<SessionResultItem> items;

    /** 结果汇总（题量/判分统计/得分）。 */
    @SerializedName("summary")
    private SessionResultSummaryInfo summary;

    public SessionResponse getSession() {
        return session;
    }

    public List<SessionResultItem> getItems() {
        return items;
    }

    public SessionResultSummaryInfo getSummary() {
        return summary;
    }
}
