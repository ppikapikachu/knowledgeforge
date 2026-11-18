package com.knowledgeforge.app.data.local;

import com.knowledgeforge.app.network.model.AuthTokenData;

/**
 * 普通用户登录凭证的本地存储接口。
 *
 * <p>整个 App 只能使用同一个 TokenStorage 实例，避免 AuthInterceptor、Repository
 * 和 TokenRefreshManager 分别读取不同的 SharedPreferences，导致请求没有携带最新令牌。</p>
 */
public interface TokenStorage {

    /** 保存登录、注册或刷新接口返回的新令牌对。 */
    void saveSession(AuthTokenData response);

    /** 获取当前 Access Token。 */
    String getAccessToken();

    /** 获取当前 Refresh Token。 */
    String getRefreshToken();

    /** 获取令牌类型，通常为 Bearer。 */
    String getTokenType();

    /** 获取当前 Access Token 的过期时间，使用毫秒时间戳。 */
    long getAccessTokenExpiresAt();

    /** 当前是否存在非空 Refresh Token。 */
    boolean hasRefreshToken();

    /** 清除当前登录会话的全部本地凭证。 */
    void clearSession();

    /**
     * 使用 Refresh Token 做比较并保存新令牌对。
     *
     * <p>只有当本地 Refresh Token 仍等于 expectedRefreshToken 时才更新。
     * 这是为了防止一个较早发起、较晚返回的刷新响应覆盖用户后来重新登录得到的新令牌。</p>
     *
     * @param expectedRefreshToken 发起本次刷新时使用的旧 Refresh Token
     * @param response             刷新接口返回的新令牌对
     * @return true 表示比较成功且已保存；false 表示本地会话已经变化，本次响应不能覆盖它
     */
    boolean replaceSessionIfRefreshTokenMatches(
            String expectedRefreshToken,
            AuthTokenData response
    );

    /**
     * 仅当本地 Refresh Token 仍与 expectedRefreshToken 一致时清除会话。
     * 防止旧刷新请求失败时误删用户刚刚重新登录或刷新得到的新会话。
     */
    boolean clearSessionIfRefreshTokenMatches(String expectedRefreshToken);

    /**
     * 当本地 Access Token 和 Refresh Token 都与请求发出时一致时清除会话。
     * 主要用于发现 Access Token 已失效、但本地根本没有 Refresh Token 的异常状态。
     */
    boolean clearSessionIfTokensMatch(
            String expectedAccessToken,
            String expectedRefreshToken
    );
}
