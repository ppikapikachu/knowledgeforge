package com.knowledgeforge.app.network.api;

import com.knowledgeforge.app.network.model.ApiResponse;
import com.knowledgeforge.app.network.model.AuthTokenData;
import com.knowledgeforge.app.network.model.UserInfo;
import com.knowledgeforge.app.network.model.UserLoginRequest;
import com.knowledgeforge.app.network.model.UserLogoutRequest;
import com.knowledgeforge.app.network.model.UserRefreshRequest;
import com.knowledgeforge.app.network.model.UserRegisterRequest;

import retrofit2.Call;
import retrofit2.http.Body;
import retrofit2.http.GET;
import retrofit2.http.POST;

/**
 * 用户认证与个人资料接口（后端 tag「普通用户」，共 5 个）。
 * 本文件只声明 HTTP 接口，不含业务逻辑；响应统一为后端封套 ApiResponse。
 * 令牌规则：
 * - register/login/refresh 成功返回令牌对（AuthTokenData）；
 * - refresh 采用令牌轮换，旧 refresh_token 用后立即作废（重放报 40101），
 *   客户端必须同时替换本地两个 token；
 * - logout 只撤销请求体中 refresh_token 对应的单个会话，不影响其他设备。
 * 其中 register/login/refresh 为公开接口（AuthInterceptor 不附加 Authorization 头）。
 */
public interface UserApiService {

    /**
     * 注册（POST /api/v1/users/register）：注册成功即自动登录，
     * 返回访问/刷新令牌与用户信息；账号重复报 40901，参数校验失败报 42201。
     *
     * @param request 注册信息（account/password 必填，nickname/avatar 可选）
     * @return 令牌对 + 用户信息
     */
    @POST("api/v1/users/register")
    Call<ApiResponse<AuthTokenData>> register(@Body UserRegisterRequest request);

    /**
     * 登录（POST /api/v1/users/login）：失败时统一提示「账号或密码错误」，
     * 不暴露账号是否存在。
     *
     * @param request 登录信息（account/password 必填，device_id/device_name 可选）
     * @return 令牌对 + 用户信息
     */
    @POST("api/v1/users/login")
    Call<ApiResponse<AuthTokenData>> login(@Body UserLoginRequest request);

    /**
     * 刷新令牌（POST /api/v1/users/refresh）：轮换机制，返回新的令牌对，
     * 旧 refresh_token 立即作废；用旧票重复刷新报 40101。
     *
     * @param request 刷新令牌（refresh_token 必填）
     * @return 新令牌对 + 用户信息
     */
    @POST("api/v1/users/refresh")
    Call<ApiResponse<AuthTokenData>> refresh(@Body UserRefreshRequest request);

    /**
     * 退出登录（POST /api/v1/users/logout）：只撤销请求体中 refresh_token
     * 对应的会话；成功响应 data 恒为 null（message=已退出登录）。
     * 调用成功后客户端应清除本地两个 token。
     *
     * @param request 要撤销的刷新令牌
     * @return data 恒为 null
     */
    @POST("api/v1/users/logout")
    Call<ApiResponse<Void>> logout(@Body UserLogoutRequest request);

    /**
     * 当前用户资料（GET /api/v1/users/me）：按 access_token 身份返回本人资料，
     * 未认证报 40101。
     *
     * @return 用户资料（id/account/nickname/avatar）
     */
    @GET("api/v1/users/me")
    Call<ApiResponse<UserInfo>> getCurrentUser();
}
