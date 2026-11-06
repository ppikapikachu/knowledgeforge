package com.knowledgeforge.app.network.api;

import com.knowledgeforge.app.network.model.ApiResponse;
import com.knowledgeforge.app.network.model.AuthTokenData;
import com.knowledgeforge.app.network.model.UserInfo;

import retrofit2.Call;
import retrofit2.http.Body;

// 用户认证、个人资料
public interface UserApiService {

    Call<ApiResponse<AuthTokenData>> register(@Body UserInfo userInfo);

    Call<ApiResponse<AuthTokenData>>
}
