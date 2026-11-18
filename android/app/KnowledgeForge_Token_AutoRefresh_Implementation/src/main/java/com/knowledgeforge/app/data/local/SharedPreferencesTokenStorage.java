package com.knowledgeforge.app.data.local;

import android.content.Context;
import android.content.SharedPreferences;

import com.knowledgeforge.app.network.model.AuthTokenData;

/**
 * 基于 SharedPreferences 的普通用户 Token 存储实现。
 *
 * <p>Access Token、Refresh Token、Token Type 和 Access Token 过期时间保存在同一个
 * SharedPreferences 文件中。更新令牌对时使用同一个 Editor 一次性写入，避免只更新其中一个令牌。</p>
 *
 * <p>本类的写操作使用 synchronized 保护，并提供“比较后更新/清除”方法，避免迟到的刷新响应
 * 覆盖或删除其他请求刚刚建立的新登录会话。</p>
 */
public class SharedPreferencesTokenStorage implements TokenStorage {

    private static final String PREF_NAME = "kf_session";

    private static final String KEY_ACCESS_TOKEN = "access_token";
    private static final String KEY_REFRESH_TOKEN = "refresh_token";
    private static final String KEY_TOKEN_TYPE = "token_type";
    private static final String KEY_EXPIRES_AT = "expires_at";

    /** 当前 TokenStorage 实例所使用的认证凭证配置文件。 */
    private final SharedPreferences preferences;

    public SharedPreferencesTokenStorage(Context context) {
        preferences = context.getApplicationContext()
                .getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE);
    }

    /**
     * 保存登录/注册成功后返回的令牌对。
     *
     * <p>Access Token 和 Refresh Token 在同一个 Editor 中写入，不能拆成两次保存。</p>
     */
    @Override
    public synchronized void saveSession(AuthTokenData response) {
        if (response == null) {
            throw new IllegalArgumentException("Token 响应不能为空");
        }
        writeSession(response);
    }

    /** 将完整令牌对写入本地；调用方必须保证 response 有效。 */
    private void writeSession(AuthTokenData response) {
        long expiresAt = System.currentTimeMillis()
                + response.getExpiresIn() * 1000L;

        preferences.edit()
                .putString(KEY_ACCESS_TOKEN, response.getAccessToken())
                .putString(KEY_REFRESH_TOKEN, response.getRefreshToken())
                .putString(KEY_TOKEN_TYPE, isEmpty(response.getTokenType())
                        ? "Bearer" : response.getTokenType())
                .putLong(KEY_EXPIRES_AT, expiresAt)
                .apply();
    }

    @Override
    public String getAccessToken() {
        return preferences.getString(KEY_ACCESS_TOKEN, null);
    }

    @Override
    public String getRefreshToken() {
        return preferences.getString(KEY_REFRESH_TOKEN, null);
    }

    @Override
    public String getTokenType() {
        return preferences.getString(KEY_TOKEN_TYPE, "Bearer");
    }

    @Override
    public long getAccessTokenExpiresAt() {
        return preferences.getLong(KEY_EXPIRES_AT, 0L);
    }

    @Override
    public boolean hasRefreshToken() {
        return !isEmpty(getRefreshToken());
    }

    /**
     * 无条件清除当前会话。
     * 通常用于用户主动退出登录；自动刷新流程应优先使用条件清除方法。
     */
    @Override
    public synchronized void clearSession() {
        preferences.edit().clear().apply();
    }

    /**
     * 比较当前 Refresh Token 后再保存刷新响应。
     * 整个比较和写入都在同一把对象锁中，和 saveSession/clearSession 串行执行。
     */
    @Override
    public synchronized boolean replaceSessionIfRefreshTokenMatches(
            String expectedRefreshToken,
            AuthTokenData response
    ) {
        if (response == null
                || isEmpty(response.getAccessToken())
                || isEmpty(response.getRefreshToken())
                || response.getExpiresIn() <= 0L) {
            return false;
        }

        String currentRefreshToken = getRefreshToken();
        if (!sameValue(currentRefreshToken, expectedRefreshToken)) {
            return false;
        }

        writeSession(response);
        return true;
    }

    /** 只有刷新令牌仍是本次请求使用的旧令牌时，才允许清除会话。 */
    @Override
    public synchronized boolean clearSessionIfRefreshTokenMatches(
            String expectedRefreshToken
    ) {
        if (!sameValue(getRefreshToken(), expectedRefreshToken)) {
            return false;
        }

        preferences.edit().clear().apply();
        return true;
    }

    /** Access Token 与 Refresh Token 同时匹配时才清除，避免误删新会话。 */
    @Override
    public synchronized boolean clearSessionIfTokensMatch(
            String expectedAccessToken,
            String expectedRefreshToken
    ) {
        if (!sameValue(getAccessToken(), expectedAccessToken)
                || !sameValue(getRefreshToken(), expectedRefreshToken)) {
            return false;
        }

        preferences.edit().clear().apply();
        return true;
    }

    private boolean sameValue(String first, String second) {
        if (first == null) {
            return second == null;
        }
        return first.equals(second);
    }

    private boolean isEmpty(String value) {
        return value == null || value.trim().isEmpty();
    }
}
