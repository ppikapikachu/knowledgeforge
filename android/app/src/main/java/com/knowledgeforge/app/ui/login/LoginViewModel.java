package com.knowledgeforge.app.ui.login;

import androidx.lifecycle.LiveData;
import androidx.lifecycle.MutableLiveData;
import androidx.lifecycle.ViewModel;

import com.knowledgeforge.app.data.repository.AuthRepository;
import com.knowledgeforge.app.network.callback.ApiCallback;
import com.knowledgeforge.app.network.model.ApiException;
import com.knowledgeforge.app.network.model.UserInfo;
import com.knowledgeforge.app.ui.common.Event;

/**
 * ViewModel 不应该持有 Activity，也不应该直接调用
 */
public class LoginViewModel extends ViewModel {

    private final AuthRepository authRepository;

    // 登录页面状态
    private final MutableLiveData<LoginUiState> uiState =
            new MutableLiveData<>(LoginUiState.idle());

    // 登录成功事件
    private final MutableLiveData<Event<UserInfo>> loginSuccess =
            new MutableLiveData<>();

    // 防止重复发起登录请求
    private boolean requestRunning = false;

    public LoginViewModel(AuthRepository authRepository) {
        // Repository 是外部依赖，ViewModel 不应该自己创建它。
        this.authRepository = authRepository;
    }

    /**
     * 对外提供只读状态
     */
    public LiveData<LoginUiState> getUiState() {
        return uiState;
    }

    /**
     * 对外提供登录成功事件
     */
    public LiveData<Event<UserInfo>> getLoginSuccess() {
        return loginSuccess;
    }

    /**
     * 登录
     */
    public void login(String account, String password) {

        // 防止重复请求
        if (requestRunning) {
            return;
        }

        // 账号可以去除首尾空格
        String finalAccount = account == null
                ? ""
                : account.trim();

        // 密码不要 trim，避免改变用户真正输入的密码
        if (finalAccount.isEmpty()) {
            uiState.setValue(
                    LoginUiState.error("请输入账号")
            );
            return;
        }

        if (password == null || password.isEmpty()) {
            uiState.setValue(
                    LoginUiState.error("请输入密码")
            );
            return;
        }

        // 开始请求
        requestRunning = true;

        uiState.setValue(LoginUiState.loading());

        // 调用 Repository
        authRepository.login(
                finalAccount,
                password,
                new ApiCallback<UserInfo>() {

                    @Override
                    public void onSuccess(UserInfo user) {

                        requestRunning = false;

                        // 登录成功，恢复页面正常状态
                        uiState.setValue(LoginUiState.idle());

                        // 发送一次性成功事件
                        loginSuccess.setValue(new Event<>(user));
                    }

                    @Override
                    public void onError(ApiException error) {

                        requestRunning = false;

                        String message = error == null
                                ? "登录失败，请稍后重试"
                                : error.getMessage();

                        if (message == null || message.trim().isEmpty()) {
                            message = "登录失败，请稍后重试";
                        }

                        uiState.setValue(
                                LoginUiState.error(message)
                        );
                    }
                }
        );
    }
}