package com.knowledgeforge.app.network.api;

import com.google.gson.JsonObject;
import com.knowledgeforge.app.network.model.ApiResponse;
import com.knowledgeforge.app.network.model.AuthTokenData;
import com.knowledgeforge.app.network.model.KnowledgePointsResponse;
import com.knowledgeforge.app.network.model.PageResponse;
import com.knowledgeforge.app.network.model.QuestionBank;
import com.knowledgeforge.app.network.model.UserInfo;

import retrofit2.Call;
import retrofit2.http.Body;
import retrofit2.http.GET;
import retrofit2.http.POST;
import retrofit2.http.Path;
import retrofit2.http.Query;

/** 只负责声明后端 HTTP 接口，不在这里写业务逻辑。 */
public interface ApiService {

    // Auth Request Schema 在当前 API Reference 中没有完整列出；请求体先保留 JsonObject，
    // 实际字段必须按后端 /openapi.json 或 Swagger 的 Request Schema 填写。
    @POST("api/v1/users/login")
    Call<ApiResponse<AuthTokenData>> login(@Body JsonObject requestBody);

    @POST("api/v1/users/register")
    Call<ApiResponse<AuthTokenData>> register(@Body JsonObject requestBody);

    @POST("api/v1/users/refresh")
    Call<ApiResponse<AuthTokenData>> refreshToken(@Body JsonObject requestBody);

    @GET("api/v1/users/me")
    Call<ApiResponse<UserInfo>> getCurrentUser();

    @GET("api/v1/practice/question-banks")
    Call<ApiResponse<PageResponse<QuestionBank>>> getQuestionBanks(
            @Query("page") int page,
            @Query("page_size") int pageSize,
            @Query("keyword") String keyword
    );

    @GET("api/v1/practice/question-banks/{qb_id}")
    Call<ApiResponse<QuestionBank>> getQuestionBankDetail(@Path("qb_id") int questionBankId);

    @GET("api/v1/practice/question-banks/{qb_id}/knowledge-points")
    Call<ApiResponse<KnowledgePointsResponse>> getKnowledgePoints(
            @Path("qb_id") int questionBankId
    );
}
