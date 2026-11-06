package com.knowledgeforge.app.data.local;

import com.knowledgeforge.app.network.model.AuthTokenData;

public interface TokenStorage {

    void saveSession(AuthTokenData response);

    String getAccessToken();

    String getRefreshToken();

    String getTokenType();

    long getAccessTokenExpiresAt();

    boolean hasRefreshToken();

    void clearSession();
}
