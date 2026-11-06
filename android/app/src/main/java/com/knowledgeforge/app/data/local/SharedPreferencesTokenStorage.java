package com.knowledgeforge.app.data.local;

import android.content.Context;
import android.content.SharedPreferences;

import com.knowledgeforge.app.network.model.AuthTokenData;

public class SharedPreferencesTokenStorage implements TokenStorage{
    private static final String PREF_NAME = "kf_session";

    private static final String KEY_ACCESS_TOKEN = "access_token";
    private static final String KEY_REFRESH_TOKEN = "refresh_token";
    private static final String KEY_TOKEN_TYPE = "token_type";
    private static final String KEY_EXPIRES_AT = "expires_at";

    public static SharedPreferences preferences;

    public SharedPreferencesTokenStorage(Context context) {
        preferences = context.getApplicationContext().getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE);
    }

    @Override
    public void saveSession(AuthTokenData response) {
        long expiresAt = System.currentTimeMillis()
                + response.getExpiresIn() * 1000L;

        preferences.edit()
                .putString(KEY_ACCESS_TOKEN, response.getAccessToken())
                .putString(KEY_REFRESH_TOKEN, response.getRefreshToken())
                .putString(KEY_TOKEN_TYPE, response.getTokenType())
                .putLong(KEY_EXPIRES_AT, expiresAt)
                .apply();
    }

    @Override
    public String getAccessToken() {
        return preferences.getString(KEY_ACCESS_TOKEN,null);
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
        return preferences.getLong(KEY_EXPIRES_AT, 0);
    }

    @Override
    public boolean hasRefreshToken() {
        String token = getRefreshToken();
        return token != null && !token.isEmpty();
    }

    @Override
    public void clearSession() {
        preferences.edit().clear().apply();
    }
}
