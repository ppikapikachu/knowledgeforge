package com.knowledgeforge.app.network;

import android.content.Context;

import com.knowledgeforge.app.BuildConfig;
import com.knowledgeforge.app.network.api.ApiService;
import com.knowledgeforge.app.network.auth.AuthInterceptor;
import com.knowledgeforge.app.network.auth.TokenManager;

import java.util.concurrent.TimeUnit;

import okhttp3.OkHttpClient;
import okhttp3.logging.HttpLoggingInterceptor;
import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;

/** 全应用共用一份 Retrofit / OkHttp 实例。 */
public final class ApiClient {
    private static volatile ApiClient instance;
    private final ApiService apiService;

    private ApiClient(Context context) {
        TokenManager tokenManager = TokenManager.getInstance(context);

        HttpLoggingInterceptor logging = new HttpLoggingInterceptor();
        logging.redactHeader("Authorization");
        logging.redactHeader("Cookie");
        // BASIC 只记录请求行和响应状态，不输出登录密码、请求体或完整响应体。
        logging.setLevel(BuildConfig.DEBUG
                ? HttpLoggingInterceptor.Level.BASIC
                : HttpLoggingInterceptor.Level.NONE);

        OkHttpClient okHttpClient = new OkHttpClient.Builder()
                .addInterceptor(logging)
                .addInterceptor(new AuthInterceptor(tokenManager))
                .connectTimeout(15, TimeUnit.SECONDS)
                .readTimeout(30, TimeUnit.SECONDS)
                .writeTimeout(30, TimeUnit.SECONDS)
                .build();

        Retrofit retrofit = new Retrofit.Builder()
                .baseUrl(ApiConfig.BASE_URL)
                .client(okHttpClient)
                .addConverterFactory(GsonConverterFactory.create())
                .build();

        apiService = retrofit.create(ApiService.class);
    }

    public static ApiClient getInstance(Context context) {
        if (instance == null) {
            synchronized (ApiClient.class) {
                if (instance == null) {
                    instance = new ApiClient(context.getApplicationContext());
                }
            }
        }
        return instance;
    }

    public ApiService getApiService() {
        return apiService;
    }
}
