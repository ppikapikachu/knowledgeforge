package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

import java.util.List;

/**
 * 会话答题记录列表（对应后端 schema SessionAnswersResponse，
 * 接口 GET /api/v1/practice/sessions/{session_id}/answers）。
 * 每次提交追加一条记录，按提交时间正序（created_at 正序、id 升序）返回。
 */
public class SessionAnswersResponse {

    /** 练习会话 ID。 */
    @SerializedName("session_id")
    private int sessionId;

    /** 答题记录列表（按提交时间正序）。 */
    @SerializedName("answers")
    private List<SessionAnswerRecordItem> answers;

    public int getSessionId() {
        return sessionId;
    }

    public List<SessionAnswerRecordItem> getAnswers() {
        return answers;
    }
}
