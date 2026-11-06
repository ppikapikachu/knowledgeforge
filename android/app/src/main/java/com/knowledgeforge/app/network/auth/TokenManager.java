package com.knowledgeforge.app.network.auth;

import android.content.Context;
import android.content.SharedPreferences;

/** 集中管理用户 Token；网络层和业务层不要各自读写 SharedPreferences。 */
public final class TokenManager {
    private static final String PREF_NAME = "knowledgeforge_auth";
    private static final String KEY_ACCESS_TOKEN = "access_token";
    private static final String KEY_REFRESH_TOKEN = "refresh_token";

    private static volatile TokenManager instance;
    private final SharedPreferences preferences;

    private TokenManager(Context context) {
        Context appContext = context.getApplicationContext();
        preferences = appContext.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE);
    }

    public static TokenManager getInstance(Context context) {
        if (instance == null) {
            synchronized (TokenManager.class) {
                if (instance == null) {
                    instance = new TokenManager(context);
                }
            }
        }
        return instance;
    }

    public String getAccessToken() {
        return preferences.getString(KEY_ACCESS_TOKEN, null);
    }

    public String getRefreshToken() {
        return preferences.getString(KEY_REFRESH_TOKEN, null);
    }

    /** 一次 Editor 同时写入两个 token，适用于登录和 refresh 轮换后的替换。 */
    public void saveTokens(String accessToken, String refreshToken) {
        preferences.edit()
                .putString(KEY_ACCESS_TOKEN, accessToken)
                .putString(KEY_REFRESH_TOKEN, refreshToken)
                .apply();
    }

    public void clearTokens() {
        preferences.edit()
                .remove(KEY_ACCESS_TOKEN)
                .remove(KEY_REFRESH_TOKEN)
                .apply();
    }

    public boolean hasAccessToken() {
        String token = getAccessToken();
        return token != null && !token.trim().isEmpty();
    }
}
