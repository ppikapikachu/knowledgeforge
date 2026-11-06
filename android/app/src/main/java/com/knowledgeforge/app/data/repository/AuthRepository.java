package com.knowledgeforge.app.data.repository;

import com.knowledgeforge.app.data.local.TokenStorage;
import com.knowledgeforge.app.network.ApiCallExecutor;
import com.knowledgeforge.app.network.api.UserApiService;
import com.knowledgeforge.app.network.callback.ApiCallback;
import com.knowledgeforge.app.network.model.ApiException;
import com.knowledgeforge.app.network.model.AuthTokenData;
import com.knowledgeforge.app.network.model.UserInfo;
import com.knowledgeforge.app.network.model.UserLoginRequest;

/**
 * 用户认证 Repository。
 * <p>
 * 负责协调远程认证接口和本地 Token 存储。
 */
public class AuthRepository {

    private final UserApiService userApiService;

    private final TokenStorage tokenStorage;

    public AuthRepository(
            UserApiService userApiService,
            TokenStorage tokenStorage
    ) {
        this.userApiService = userApiService;
        this.tokenStorage = tokenStorage;
    }

    /**
     * 普通用户登录
     */
    public void login(
            String account,
            String password,
            ApiCallback<UserInfo> callback
    ) {

        // 1. 创建请求参数
        UserLoginRequest request =
                new UserLoginRequest(account, password);

        // 2. 调用统一网络执行器
        ApiCallExecutor.enqueue(
                userApiService.login(request),
                new ApiCallback<AuthTokenData>() {

                    @Override
                    public void onSuccess(AuthTokenData data) {

                        // 3. 检查登录响应
                        if (data == null
                                || isEmpty(data.getAccessToken())
                                || isEmpty(data.getRefreshToken())
                                || data.getUser() == null) {

                            callback.onError(
                                    new ApiException(
                                            -1,
                                            null,
                                            "登录响应数据不完整",
                                            null
                                    )
                            );
                            return;
                        }

                        // 4. 保存 Token
                        try {
                            tokenStorage.saveSession(data);

                        } catch (Exception e) {

                            callback.onError(
                                    new ApiException(
                                            -1,
                                            null,
                                            "登录凭证保存失败",
                                            null,
                                            e
                                    )
                            );
                            return;
                        }

                        // 5. 将用户资料返回给 ViewModel
                        callback.onSuccess(data.getUser());
                    }

                    @Override
                    public void onError(ApiException error) {

                        // 网络错误、HTTP 错误、业务错误统一向上传递
                        callback.onError(error);
                    }
                }
        );
    }

    private boolean isEmpty(String value) {
        return value == null || value.trim().isEmpty();
    }
}