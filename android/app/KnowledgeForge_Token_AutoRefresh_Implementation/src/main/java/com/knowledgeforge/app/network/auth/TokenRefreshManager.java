package com.knowledgeforge.app.network.auth;

import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.annotations.SerializedName;
import com.knowledgeforge.app.data.local.TokenStorage;
import com.knowledgeforge.app.network.api.UserApiService;
import com.knowledgeforge.app.network.model.ApiException;
import com.knowledgeforge.app.network.model.ApiResponse;
import com.knowledgeforge.app.network.model.AuthTokenData;
import com.knowledgeforge.app.network.model.UserRefreshRequest;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

import okhttp3.ResponseBody;
import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

/**
 * 普通用户 Access Token 自动刷新管理器。
 *
 * <p>职责：</p>
 * <ul>
 *     <li>当受保护接口返回业务错误码 40101 时，使用 Refresh Token 换取新的令牌对；</li>
 *     <li>同一令牌会话的多个并发 40101 请求共用一次刷新请求（Single Flight）；</li>
 *     <li>刷新成功后同时保存新 Access Token 和新 Refresh Token；</li>
 *     <li>只在后端明确确认 Refresh Token 无效（业务码 40101）时清除会话并通知 App；</li>
 *     <li>网络超时、断网、服务器 5xx 等临时失败不清除本地令牌，也不强制跳登录页；</li>
 *     <li>刷新响应迟到时，通过 TokenStorage 的条件更新保护后来建立的新登录会话。</li>
 * </ul>
 *
 * <p>本类使用 Retrofit enqueue 异步执行，绝不在主线程 wait/sleep，避免刷新回调因主线程阻塞而死锁。</p>
 */
public final class TokenRefreshManager {

    /** 后端用于表示 Access/Refresh 认证凭证失效的业务错误码。 */
    public static final int API_CODE_UNAUTHENTICATED = 40101;

    private static final Gson GSON = new Gson();

    private final UserApiService userApiService;
    private final TokenStorage tokenStorage;

    /** 保护刷新状态及等待队列。 */
    private final Object lock = new Object();

    /** 当前是否有一个 Refresh Token 请求正在执行。 */
    private boolean refreshing;

    /** 当前刷新请求使用的 Refresh Token 快照。 */
    private String refreshingRefreshToken;

    /** 正在等待当前刷新结果的原始业务请求回调。 */
    private final List<RefreshCallback> waitingCallbacks = new ArrayList<>();

    /** 新会话在旧会话刷新期间遇到 40101 时，先排队，旧刷新结束后再判断是否需要刷新。 */
    private final List<PendingRefresh> deferredRequests = new ArrayList<>();

    public TokenRefreshManager(UserApiService userApiService, TokenStorage tokenStorage) {
        if (userApiService == null || tokenStorage == null) {
            throw new IllegalArgumentException("UserApiService 和 TokenStorage 不能为空");
        }
        this.userApiService = userApiService;
        this.tokenStorage = tokenStorage;
    }

    /**
     * 刷新 Access Token，或者复用其他请求已经刷新的结果。
     *
     * @param failedAccessToken 返回 40101 的原请求实际使用的 Access Token
     * @param callback          刷新结果回调；成功时返回当前可用 Access Token
     */
    public void refreshIfNeeded(String failedAccessToken, RefreshCallback callback) {
        if (callback == null) {
            return;
        }
        if (isEmpty(failedAccessToken)) {
            callback.onFailure(new ApiException(-1, API_CODE_UNAUTHENTICATED,
                    "请求没有可用的 Access Token", null));
            return;
        }

        String accessTokenToUse = null;
        String refreshTokenToUse = null;
        String missingRefreshToken = null;
        boolean refreshTokenMissing = false;
        boolean shouldStartRefresh = false;
        boolean shouldDefer = false;

        synchronized (lock) {
            // 其他请求可能已经刷新成功。若本地 Access Token 已变化，直接复用新令牌即可。
            String currentAccessToken = tokenStorage.getAccessToken();
            if (!isEmpty(currentAccessToken)
                    && !currentAccessToken.equals(failedAccessToken)) {
                accessTokenToUse = currentAccessToken;
            } else {
                String currentRefreshToken = tokenStorage.getRefreshToken();
                if (isEmpty(currentRefreshToken)) {
                    missingRefreshToken = currentRefreshToken;
                    refreshTokenMissing = true;
                } else if (refreshing
                        && !currentRefreshToken.equals(refreshingRefreshToken)) {
                    // 当前刷新属于另一个登录会话。不能把新会话的请求加入旧会话的等待队列。
                    deferredRequests.add(new PendingRefresh(failedAccessToken, callback));
                    shouldDefer = true;
                } else {
                    waitingCallbacks.add(callback);
                    if (!refreshing) {
                        refreshing = true;
                        refreshingRefreshToken = currentRefreshToken;
                        refreshTokenToUse = currentRefreshToken;
                        shouldStartRefresh = true;
                    }
                }
            }
        }

        if (!isEmpty(accessTokenToUse)) {
            callback.onSuccess(accessTokenToUse);
            return;
        }
        if (shouldDefer) {
            return;
        }
        if (refreshTokenMissing) {
            handleMissingRefreshToken(failedAccessToken, missingRefreshToken, callback);
            return;
        }
        if (shouldStartRefresh) {
            executeRefresh(refreshTokenToUse);
        }
    }

    /** 发起唯一的 Refresh Token 网络请求。 */
    private void executeRefresh(String refreshTokenUsed) {
        userApiService.refresh(new UserRefreshRequest(refreshTokenUsed))
                .enqueue(new Callback<ApiResponse<AuthTokenData>>() {
                    @Override
                    public void onResponse(Call<ApiResponse<AuthTokenData>> call,
                                           Response<ApiResponse<AuthTokenData>> response) {
                        if (!response.isSuccessful()) {
                            ApiException error = parseHttpError(
                                    response.code(), response.errorBody());
                            handleRefreshError(refreshTokenUsed, error);
                            return;
                        }

                        ApiResponse<AuthTokenData> body = response.body();
                        if (body == null) {
                            finishFlightFailure(new ApiException(response.code(), null,
                                    "刷新登录凭证失败：服务器响应为空", null));
                            return;
                        }
                        if (body.getCode() == null) {
                            finishFlightFailure(new ApiException(response.code(), null,
                                    "刷新登录凭证失败：响应缺少业务状态码", null));
                            return;
                        }
                        if (body.getCode() != 0) {
                            ApiException error = new ApiException(response.code(),
                                    body.getCode(), body.getMessage(), null);
                            handleRefreshError(refreshTokenUsed, error);
                            return;
                        }

                        AuthTokenData newTokenData = body.getData();
                        if (!isValidTokenData(newTokenData)) {
                            finishFlightFailure(new ApiException(response.code(), null,
                                    "刷新登录凭证失败：服务器返回的令牌数据不完整", null));
                            return;
                        }

                        // 比较旧 Refresh Token 后原子替换两个新 Token，防止迟到响应覆盖新登录状态。
                        boolean saved = tokenStorage.replaceSessionIfRefreshTokenMatches(
                                refreshTokenUsed, newTokenData);
                        if (saved) {
                            finishFlightSuccess(newTokenData.getAccessToken());
                            return;
                        }

                        // 本地令牌已经被登录、注册、退出或另一轮刷新改变，不允许写入旧响应。
                        String latestAccessToken = tokenStorage.getAccessToken();
                        if (!isEmpty(latestAccessToken)) {
                            finishFlightSuccess(latestAccessToken);
                        } else {
                            finishFlightFailure(new ApiException(-1, null,
                                    "登录状态已发生变化，请重新发起请求", null));
                        }
                    }

                    @Override
                    public void onFailure(Call<ApiResponse<AuthTokenData>> call, Throwable t) {
                        // 网络故障不是 Refresh Token 失效：保留本地凭证，允许用户恢复网络后重试。
                        String message = call.isCanceled()
                                ? "刷新登录凭证请求已取消"
                                : "暂时无法刷新登录状态，请检查网络后重试";
                        finishFlightFailure(new ApiException(-1, null, message, null, t));
                    }
                });
    }

    /**
     * 处理刷新接口的业务错误。
     * 只有明确的 40101 才认定 Refresh Token 失效；其他错误不清除本地会话。
     */
    private void handleRefreshError(String refreshTokenUsed, ApiException error) {
        if (error.getApiCode() != null
                && error.getApiCode() == API_CODE_UNAUTHENTICATED) {
            boolean cleared = tokenStorage.clearSessionIfRefreshTokenMatches(refreshTokenUsed);
            if (cleared) {
                // 先条件清除本地令牌，再通知 UI 跳转登录，避免跳转期间旧令牌仍被请求拦截器读取。
                AuthSessionEventManager.notifySessionExpired();
                finishFlightFailure(new ApiException(error.getHttpCode(),
                        error.getApiCode(), "登录状态已过期，请重新登录", error.getErrorData()));
                return;
            }

            // 旧刷新响应失败，但当前 Refresh Token 已变化：可能用户已重新登录或另一轮刷新成功。
            String latestAccessToken = tokenStorage.getAccessToken();
            if (!isEmpty(latestAccessToken)) {
                finishFlightSuccess(latestAccessToken);
            } else {
                finishFlightFailure(new ApiException(error.getHttpCode(),
                        error.getApiCode(), "登录状态已发生变化，请重新发起请求", error.getErrorData()));
            }
            return;
        }

        finishFlightFailure(error);
    }

    /** 本地有失效 Access Token、却没有 Refresh Token 时，按令牌对条件清除会话。 */
    private void handleMissingRefreshToken(String failedAccessToken,
                                           String observedRefreshToken,
                                           RefreshCallback callback) {
        boolean cleared = tokenStorage.clearSessionIfTokensMatch(
                failedAccessToken, observedRefreshToken);
        if (cleared) {
            AuthSessionEventManager.notifySessionExpired();
            callback.onFailure(new ApiException(-1, API_CODE_UNAUTHENTICATED,
                    "登录凭证不完整，请重新登录", null));
            return;
        }

        // 条件清除失败说明会话可能刚刚被其他流程改变，再读一次最新 Access Token。
        String latestAccessToken = tokenStorage.getAccessToken();
        if (!isEmpty(latestAccessToken)
                && !latestAccessToken.equals(failedAccessToken)) {
            callback.onSuccess(latestAccessToken);
            return;
        }

        // 如果检查期间另一个登录/刷新流程刚刚写入了 Refresh Token，重新走一次判断，
        // 不要把这类并发更新误报成登录失效。
        if (tokenStorage.hasRefreshToken()) {
            refreshIfNeeded(failedAccessToken, callback);
            return;
        }

        callback.onFailure(new ApiException(-1, null,
                "登录状态已发生变化，请重新发起请求", null));
    }

    /** 刷新成功：唤醒当前等待的请求，并依次处理刷新期间到来的其他会话请求。 */
    private void finishFlightSuccess(String accessToken) {
        List<RefreshCallback> callbacks;
        synchronized (lock) {
            callbacks = new ArrayList<>(waitingCallbacks);
            waitingCallbacks.clear();
            refreshing = false;
            refreshingRefreshToken = null;
        }

        for (RefreshCallback callback : callbacks) {
            callback.onSuccess(accessToken);
        }
        processDeferredRequests();
    }

    /** 刷新失败：将同一刷新批次的错误交给所有等待请求，然后继续处理延迟队列。 */
    private void finishFlightFailure(ApiException error) {
        List<RefreshCallback> callbacks;
        synchronized (lock) {
            callbacks = new ArrayList<>(waitingCallbacks);
            waitingCallbacks.clear();
            refreshing = false;
            refreshingRefreshToken = null;
        }

        for (RefreshCallback callback : callbacks) {
            callback.onFailure(error);
        }
        processDeferredRequests();
    }

    /** 处理旧会话刷新期间进入的不同会话请求；每个请求会重新检查当前 Token。 */
    private void processDeferredRequests() {
        List<PendingRefresh> pending;
        synchronized (lock) {
            if (refreshing || deferredRequests.isEmpty()) {
                return;
            }
            pending = new ArrayList<>(deferredRequests);
            deferredRequests.clear();
        }

        for (PendingRefresh request : pending) {
            refreshIfNeeded(request.failedAccessToken, request.callback);
        }
    }

    private boolean isValidTokenData(AuthTokenData data) {
        return data != null
                && !isEmpty(data.getAccessToken())
                && !isEmpty(data.getRefreshToken())
                && data.getExpiresIn() > 0L;
    }

    /** 解析非 2xx 刷新响应中的统一错误封套，以识别后端业务码 40101。 */
    private ApiException parseHttpError(int httpCode, ResponseBody errorBody) {
        if (errorBody != null) {
            try {
                String raw = errorBody.string();
                if (!isEmpty(raw)) {
                    ApiErrorEnvelope envelope = GSON.fromJson(raw, ApiErrorEnvelope.class);
                    if (envelope != null) {
                        return new ApiException(httpCode, envelope.code,
                                isEmpty(envelope.message) ? "刷新登录凭证失败" : envelope.message,
                                envelope.data);
                    }
                }
            } catch (Exception ignored) {
                // 非 JSON 响应体由下面的 HTTP 状态码错误承接。
            }
        }
        return new ApiException(httpCode, null,
                "刷新登录凭证失败，HTTP 状态码：" + httpCode, null);
    }

    private boolean isEmpty(String value) {
        return value == null || value.trim().isEmpty();
    }

    /** 等待刷新结果的调用方接口。回调在 Retrofit 的异步回调线程（通常为主线程）执行。 */
    public interface RefreshCallback {
        void onSuccess(String accessToken);
        void onFailure(ApiException error);
    }

    /** 不同登录会话在当前刷新期间到达时暂存的请求。 */
    private static final class PendingRefresh {
        final String failedAccessToken;
        final RefreshCallback callback;

        PendingRefresh(String failedAccessToken, RefreshCallback callback) {
            this.failedAccessToken = failedAccessToken;
            this.callback = callback;
        }
    }

    private static final class ApiErrorEnvelope {
        @SerializedName("code") Integer code;
        @SerializedName("message") String message;
        @SerializedName("data") JsonElement data;
    }
}
