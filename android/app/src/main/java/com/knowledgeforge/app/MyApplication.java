package com.knowledgeforge.app;

import android.app.Application;

import com.knowledgeforge.app.data.repository.AuthRepository;
import com.knowledgeforge.app.network.ApiClient;

/**
 * 统一依赖创建Repository
 */
public class MyApplication extends Application {

    private AuthRepository authRepository;

    @Override
    public void onCreate() {
        super.onCreate();

        ApiClient apiClient = ApiClient.getInstance(this);

        authRepository = new AuthRepository(
                apiClient.getUserApiService(),
                apiClient.getTokenStorage()
        );
    }

    public AuthRepository getAuthRepository() {
        return authRepository;
    }
}