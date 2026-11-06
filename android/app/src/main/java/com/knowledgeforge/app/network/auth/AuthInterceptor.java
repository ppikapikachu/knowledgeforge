package com.knowledgeforge.app.network.auth;

import com.knowledgeforge.app.data.local.TokenStorage;

import java.io.IOException;

import okhttp3.Interceptor;
import okhttp3.Request;
import okhttp3.Response;

/** 自动为需要登录的普通用户接口添加 Bearer access_token。 */
public class AuthInterceptor implements Interceptor {
    private final TokenStorage tokenStorage;

    public AuthInterceptor(TokenStorage tokenStorage) {
        this.tokenStorage = tokenStorage;
    }

    @Override
    public Response intercept(Chain chain) throws IOException {
        Request original = chain.request();
        String path = original.url().encodedPath();

        // 登录、注册、刷新令牌不依赖当前 access_token。
        if (isPublicAuthPath(path)) {
            return chain.proceed(original);
        }

        String accessToken = tokenStorage.getAccessToken();
        if (accessToken == null || accessToken.trim().isEmpty()) {
            return chain.proceed(original);
        }

        Request authenticated = original.newBuilder()
                .header("Authorization", "Bearer " + accessToken)
                .header("Accept", "application/json")
                .build();
        return chain.proceed(authenticated);
    }

    private boolean isPublicAuthPath(String path) {
        return path.endsWith("/api/v1/users/login")
                || path.endsWith("/api/v1/users/register")
                || path.endsWith("/api/v1/users/refresh");
    }
}
