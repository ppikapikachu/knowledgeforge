package com.knowledgeforge.app.network.api;

import com.knowledgeforge.app.network.model.AnswerRecordItem;
import com.knowledgeforge.app.network.model.ApiResponse;
import com.knowledgeforge.app.network.model.PageResponse;

import retrofit2.Call;
import retrofit2.http.GET;
import retrofit2.http.Query;

/**
 * 答题记录接口（后端 tag「答题记录」中 Android 需要的 1 个）。
 * 本文件只声明 HTTP 接口，不含业务逻辑；响应统一为后端封套 ApiResponse。
 * 只返回本人记录，只读无副作用。
 */
public interface AnswerApiService {

    /**
     * 我的答题历史（GET /api/v1/answers/history）：
     * 按当前用户分页查询答题记录，可按题目 / 练习会话过滤。
     * 注意条目 is_correct 为 Integer 三态：1=正确 / 0=错误 / null=未判分。
     *
     * @param questionId        题目 ID 过滤（可选，null=全部题目）
     * @param practiceSessionId 练习会话 ID 过滤（可选，null=不限会话）
     * @param page              页码（可选，从 1 开始）
     * @param pageSize          每页条数（可选，默认 20，取值 1~100）
     * @return 答题记录分页列表
     */
    @GET("api/v1/answers/history")
    Call<ApiResponse<PageResponse<AnswerRecordItem>>> getAnswerHistory(
            @Query("question_id") Integer questionId,
            @Query("practice_session_id") Integer practiceSessionId,
            @Query("page") Integer page,
            @Query("page_size") Integer pageSize);
}
