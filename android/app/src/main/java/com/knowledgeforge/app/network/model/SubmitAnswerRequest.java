package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 提交答题请求体（对应后端 schema SubmitAnswerRequest，
 * 接口 POST /api/v1/practice/sessions/{session_id}/items/{paper_item_id}/submit）。
 * 只接受 answer / idempotency_key / time_spent_ms 三个字段；
 * 判分结果由服务端按试卷快照内的标准答案给出，客户端不传正确答案/得分等字段。
 */
public class SubmitAnswerRequest {

    /**
     * 答案（必填），按题型为不同 JSON 值（由后端题型决定序列化形态）：
     * 单选 SINGLE_CHOICE = 选项键字符串（如 "A"）；
     * 多选 MULTIPLE_CHOICE = 选项键字符串数组（如 ["A","C"]）；
     * 判断 TRUE_FALSE = 布尔值（true/false）；
     * 简答 SHORT_ANSWER = 文本字符串。
     * Gson 会把 String / Boolean / List&lt;String&gt; 原样序列化，请按题型传对应 Java 类型。
     */
    @SerializedName("answer")
    private Object answer;

    /**
     * 幂等键（必填，8~64 位）：同 key 同内容重复提交返回原答题记录（idempotent=true），
     * 同 key 不同内容报业务错误 40001 幂等冲突，新 key 视为新一次尝试追加记录。
     */
    @SerializedName("idempotency_key")
    private String idempotencyKey;

    /** 本题作答耗时（可选，毫秒，非负，上限 24 小时即 86400000；仅作统计参考）。 */
    @SerializedName("time_spent_ms")
    private Long timeSpentMs;

    public SubmitAnswerRequest(Object answer, String idempotencyKey) {
        this.answer = answer;
        this.idempotencyKey = idempotencyKey;
    }

    public void setTimeSpentMs(Long timeSpentMs) {
        this.timeSpentMs = timeSpentMs;
    }

    public Object getAnswer() {
        return answer;
    }

    public String getIdempotencyKey() {
        return idempotencyKey;
    }

    public Long getTimeSpentMs() {
        return timeSpentMs;
    }
}
