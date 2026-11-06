package com.knowledgeforge.app.network;

import android.content.Context;

import com.knowledgeforge.app.BuildConfig;
import com.knowledgeforge.app.data.local.SharedPreferencesTokenStorage;
import com.knowledgeforge.app.data.local.TokenStorage;
import com.knowledgeforge.app.network.api.AnswerApiService;
import com.knowledgeforge.app.network.api.PracticeApiService;
import com.knowledgeforge.app.network.api.StatisticsApiService;
import com.knowledgeforge.app.network.api.UserApiService;
import com.knowledgeforge.app.network.auth.AuthInterceptor;

import java.util.concurrent.TimeUnit;

import okhttp3.OkHttpClient;
import okhttp3.logging.HttpLoggingInterceptor;
import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;

/**
 * 全应用共用一份 Retrofit / OkHttp 实例。
 * 负责构建 HTTP 客户端与 Retrofit，并按业务域创建/持有 4 个接口声明：
 * UserApiService（用户认证与资料）、PracticeApiService（练习）、
 * StatisticsApiService（个人中心统计）、AnswerApiService（答题记录）。
 * 网络日志脱敏 Authorization/Cookie 头；AuthInterceptor 自动附加 Bearer 令牌。
 */
public final class ApiClient {
    private static volatile ApiClient instance;

    /** 用户认证与个人资料接口。 */
    private final UserApiService userApiService;
    /** 练习相关接口（题库选择/组卷/会话练习/历史列表）。 */
    private final PracticeApiService practiceApiService;
    /** 个人中心统计接口。 */
    private final StatisticsApiService statisticsApiService;
    /** 答题记录接口。 */
    private final AnswerApiService answerApiService;

    private final TokenStorage tokenStorage;

    private ApiClient(Context context) {
        tokenStorage = new SharedPreferencesTokenStorage(context);
        HttpLoggingInterceptor logging = new HttpLoggingInterceptor();
        logging.redactHeader("Authorization");
        logging.redactHeader("Cookie");
        // BASIC 只记录请求行和响应状态，不输出登录密码、请求体或完整响应体。
        logging.setLevel(BuildConfig.DEBUG
                ? HttpLoggingInterceptor.Level.BASIC
                : HttpLoggingInterceptor.Level.NONE);

        OkHttpClient okHttpClient = new OkHttpClient.Builder()
                .addInterceptor(logging)
                .addInterceptor(new AuthInterceptor(tokenStorage))
                .connectTimeout(15, TimeUnit.SECONDS)
                .readTimeout(30, TimeUnit.SECONDS)
                .writeTimeout(30, TimeUnit.SECONDS)
                .build();

        Retrofit retrofit = new Retrofit.Builder()
                .baseUrl(ApiConfig.BASE_URL)
                .client(okHttpClient)
                .addConverterFactory(GsonConverterFactory.create())
                .build();

        userApiService = retrofit.create(UserApiService.class);
        practiceApiService = retrofit.create(PracticeApiService.class);
        statisticsApiService = retrofit.create(StatisticsApiService.class);
        answerApiService = retrofit.create(AnswerApiService.class);
    }

    /** 获取单例（内部持有 ApplicationContext，传任意 Context 即可）。 */
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

    /** 用户认证与个人资料接口。 */
    public UserApiService getUserApiService() {
        return userApiService;
    }

    /** 练习相关接口。 */
    public PracticeApiService getPracticeApiService() {
        return practiceApiService;
    }

    /** 个人中心统计接口。 */
    public StatisticsApiService getStatisticsApiService() {
        return statisticsApiService;
    }

    /** 答题记录接口。 */
    public AnswerApiService getAnswerApiService() {
        return answerApiService;
    }


    public TokenStorage getTokenStorage() {
        return tokenStorage;
    }
}
