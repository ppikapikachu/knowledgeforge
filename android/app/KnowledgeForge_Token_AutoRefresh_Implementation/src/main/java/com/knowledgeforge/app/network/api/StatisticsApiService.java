package com.knowledgeforge.app.network.api;

import com.knowledgeforge.app.network.model.ApiResponse;
import com.knowledgeforge.app.network.model.UserStatisticsResponse;

import retrofit2.Call;
import retrofit2.http.GET;

/**
 * 个人中心统计接口（后端 tag「普通用户」中 Android 需要的 1 个）。
 * 本文件只声明 HTTP 接口，不含业务逻辑；响应统一为后端封套 ApiResponse。
 */
public interface StatisticsApiService {

    /**
     * 个人中心统计（GET /api/v1/users/me/statistics）：
     * 返回本人答题表现与练习表现摘要；正确率在样本不足时不给具体数值，
     * 由 display_status（available|insufficient_samples）说明原因。
     *
     * @return 答题表现摘要 + 练习表现摘要
     */
    @GET("api/v1/users/me/statistics")
    Call<ApiResponse<UserStatisticsResponse>> getMyStatistics();
}
