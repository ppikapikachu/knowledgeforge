package com.knowledgeforge.app.network;

import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.annotations.SerializedName;
import com.knowledgeforge.app.network.auth.TokenRefreshManager;
import com.knowledgeforge.app.network.callback.ApiCallback;
import com.knowledgeforge.app.network.model.ApiException;
import com.knowledgeforge.app.network.model.ApiResponse;

import okhttp3.Request;
import okhttp3.ResponseBody;
import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

/**
 * 全 App 统一网络请求执行器。
 *
 * <p>统一负责：</p>
 * <ol>
 *     <li>执行 Retrofit 请求；</li>
 *     <li>解析 HTTP 状态和后端 ApiResponse 业务封套；</li>
 *     <li>当受保护接口明确返回 40101 时，交给 TokenRefreshManager 刷新令牌；</li>
 *     <li>刷新成功后，使用新的 Authorization 头重试原请求一次；</li>
 *     <li>重试请求不再触发第二次自动刷新，避免无限循环。</li>
 * </ol>
 *
 * <p>本类不持有 Activity，不负责页面跳转。Refresh Token 彻底失效时由
 * TokenRefreshManager 通知 AuthSessionEventManager，MainActivity 再负责导航到登录页。</p>
 */
public final class ApiCallExecutor {

    private static final Gson GSON = new Gson();

    /**
     * 由 ApiClient 在创建完 UserApiService 后注入全局刷新管理器。
     * volatile 确保网络请求线程能看到初始化完成的实例。
     */
    private static volatile TokenRefreshManager tokenRefreshManager;

    private ApiCallExecutor() {
    }

    /** 设置全 App 共用的 Token 刷新管理器。 */
    public static void setTokenRefreshManager(TokenRefreshManager manager) {
        tokenRefreshManager = manager;
    }

    /**
     * 执行普通 API 请求。
     *
     * @param call     Retrofit 请求
     * @param callback 统一业务回调
     */
    public static <T> void enqueue(Call<ApiResponse<T>> call, ApiCallback<T> callback) {
        enqueueInternal(call, callback, true);
    }

    /**
     * 内部请求执行方法。
     *
     * @param call             当前 Retrofit 请求
     * @param callback         原始业务请求的回调
     * @param allowAutoRefresh true 表示遇到 40101 时可以自动刷新；false 表示这是刷新后的唯一一次重试
     */
    private static <T> void enqueueInternal(
            Call<ApiResponse<T>> call,
            ApiCallback<T> callback,
            boolean allowAutoRefresh
    ) {
        call.enqueue(new Callback<ApiResponse<T>>() {
            @Override
            public void onResponse(Call<ApiResponse<T>> executedCall,
                                   Response<ApiResponse<T>> response) {
                // response.raw().request() 是经过 OkHttp Interceptor 后真正发出的请求，
                // 能读取 AuthInterceptor 实际添加的 Authorization 头。
                Request sentRequest = response.raw().request();

                // HTTP 层非 2xx：先解析后端错误封套，再判断是否为登录失效 40101。
                if (!response.isSuccessful()) {
                    ApiException error = parseHttpError(
                            response.code(), response.errorBody());
                    handleApiError(executedCall, sentRequest, callback,
                            error, allowAutoRefresh);
                    return;
                }

                ApiResponse<T> body = response.body();
                if (body == null) {
                    callback.onError(new ApiException(response.code(), null,
                            "服务器返回内容为空", null));
                    return;
                }

                if (body.getCode() == null) {
                    callback.onError(new ApiException(response.code(), null,
                            "服务器响应格式不正确（缺少 code）", null));
                    return;
                }

                // HTTP 200 也可能包含业务层错误，例如登录过期 40101。
                if (body.getCode() != 0) {
                    ApiException error = new ApiException(response.code(),
                            body.getCode(), body.getMessage(), null);
                    handleApiError(executedCall, sentRequest, callback,
                            error, allowAutoRefresh);
                    return;
                }

                callback.onSuccess(body.getData());
            }

            @Override
            public void onFailure(Call<ApiResponse<T>> executedCall, Throwable t) {
                if (executedCall.isCanceled()) {
                    callback.onError(new ApiException(-1, null,
                            "请求已取消", null, t));
                } else {
                    callback.onError(new ApiException(-1, null,
                            "网络请求失败，请检查网络连接", null, t));
                }
            }
        });
    }

    /**
     * 处理统一 API 错误。
     * 只有受保护接口明确返回业务码 40101 时才尝试刷新；其他错误原样交给调用方。
     */
    private static <T> void handleApiError(
            Call<ApiResponse<T>> originalCall,
            Request sentRequest,
            ApiCallback<T> callback,
            ApiException error,
            boolean allowAutoRefresh
    ) {
        if (!allowAutoRefresh
                || error.getApiCode() == null
                || error.getApiCode() != TokenRefreshManager.API_CODE_UNAUTHENTICATED
                || isAuthenticationEndpoint(originalCall.request().url().encodedPath())) {
            callback.onError(error);
            return;
        }

        // 如果请求实际上没有携带 Bearer Token，就不能把它视为登录会话过期。
        String failedAccessToken = extractBearerToken(
                sentRequest.header("Authorization"));
        if (isEmpty(failedAccessToken)) {
            callback.onError(error);
            return;
        }

        TokenRefreshManager manager = tokenRefreshManager;
        if (manager == null) {
            // 正常情况下 ApiClient 会先初始化 manager；保留防御处理，避免空指针崩溃。
            callback.onError(error);
            return;
        }

        manager.refreshIfNeeded(failedAccessToken,
                new TokenRefreshManager.RefreshCallback() {
                    @Override
                    public void onSuccess(String newAccessToken) {
                        // 刷新成功后重新创建 Retrofit Call。AuthInterceptor 会自动读取新 Token。
                        // allowAutoRefresh=false 保证这次重试即使再次返回 40101 也不会无限刷新。
                        if (!originalCall.isCanceled()) {
                            enqueueInternal(originalCall.clone(), callback, false);
                        }
                    }

                    @Override
                    public void onFailure(ApiException refreshError) {
                        // 网络暂时不可用时把刷新错误反馈给当前页面；会话真正失效时，
                        // TokenRefreshManager 已经另行通知全局事件管理器，由 MainActivity 跳登录页。
                        callback.onError(refreshError == null ? error : refreshError);
                    }
                });
    }

    /**
     * 登录、注册、刷新、退出登录接口不参与普通业务请求的自动刷新。
     * 尤其登录接口的 40101 可能表示账号/密码错误，不能因此刷新或强制退出。
     */
    private static boolean isAuthenticationEndpoint(String path) {
        return path.endsWith("/api/v1/users/login")
                || path.endsWith("/api/v1/users/register")
                || path.endsWith("/api/v1/users/refresh")
                || path.endsWith("/api/v1/users/logout");
    }

    /** 从真实请求的 Authorization 头中提取 Bearer 后面的 Access Token。 */
    private static String extractBearerToken(String authorization) {
        if (isEmpty(authorization)) {
            return null;
        }
        String prefix = "Bearer ";
        if (!authorization.regionMatches(true, 0, prefix, 0, prefix.length())) {
            return null;
        }
        String token = authorization.substring(prefix.length()).trim();
        return isEmpty(token) ? null : token;
    }

    /** 解析非 2xx 响应中的错误封套；业务 code 保留给 40101 判断。 */
    private static ApiException parseHttpError(int httpCode, ResponseBody errorBody) {
        if (errorBody != null) {
            try {
                String raw = errorBody.string();
                if (!isEmpty(raw)) {
                    ApiErrorEnvelope envelope = GSON.fromJson(raw, ApiErrorEnvelope.class);
                    if (envelope != null) {
                        return new ApiException(httpCode, envelope.code,
                                envelope.message == null ? "请求失败" : envelope.message,
                                envelope.data);
                    }
                }
            } catch (Exception ignored) {
                // 非 JSON 错误体时，回退到 HTTP 状态码提示。
            }
        }
        return new ApiException(httpCode, null,
                "HTTP 请求失败，状态码：" + httpCode, null);
    }

    private static boolean isEmpty(String value) {
        return value == null || value.trim().isEmpty();
    }

    /** 后端非 2xx 错误响应的统一封套结构。 */
    private static class ApiErrorEnvelope {
        @SerializedName("code") Integer code;
        @SerializedName("message") String message;
        @SerializedName("data") JsonElement data;
    }
}
