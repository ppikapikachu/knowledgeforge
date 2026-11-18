package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 组卷结果（对应后端 schema AssemblePaperResponse，
 * 接口 POST /api/v1/practice/papers/assemble 的 data）。
 * 同一 Idempotency-Key 重复请求返回原试卷/原会话且 idempotent=true（不重复建卷）。
 */
public class AssemblePaperResponse {

    /** 新建（或幂等复用）的试卷快照。 */
    @SerializedName("paper")
    private PaperResponse paper;

    /** 自动创建的首个练习会话（幂等复用的旧卷可能为 null）。 */
    @SerializedName("session")
    private SessionResponse session;

    /** 是否为幂等复用结果（true=命中 Idempotency-Key 缓存，返回原卷原会话）。 */
    @SerializedName("idempotent")
    private boolean idempotent;

    public PaperResponse getPaper() {
        return paper;
    }

    public SessionResponse getSession() {
        return session;
    }

    public boolean isIdempotent() {
        return idempotent;
    }
}
