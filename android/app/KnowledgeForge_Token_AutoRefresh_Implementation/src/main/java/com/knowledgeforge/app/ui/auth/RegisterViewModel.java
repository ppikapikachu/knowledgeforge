package com.knowledgeforge.app.ui.auth;

import androidx.lifecycle.LiveData;
import androidx.lifecycle.MutableLiveData;
import androidx.lifecycle.ViewModel;

import com.knowledgeforge.app.data.repository.AuthRepository;
import com.knowledgeforge.app.network.callback.ApiCallback;
import com.knowledgeforge.app.network.model.ApiException;
import com.knowledgeforge.app.network.model.UserInfo;
import com.knowledgeforge.app.ui.common.Event;

import java.util.regex.Pattern;

public class RegisterViewModel extends ViewModel {

    private final AuthRepository authRepository;

    private final MutableLiveData<RegisterUiState> uiState =
            new MutableLiveData<>(RegisterUiState.idle());

    private final MutableLiveData<Event<UserInfo>> registerSuccess =
            new MutableLiveData<>();

    private boolean requestRunning = false;

    // 账号：4-64 位，只允许字母、数字、. _ - @
    private static final Pattern ACCOUNT_PATTERN =
            Pattern.compile("^[A-Za-z0-9._@-]{4,64}$");

    public RegisterViewModel(AuthRepository authRepository) {
        this.authRepository = authRepository;
    }

    public LiveData<RegisterUiState> getUiState() {
        return uiState;
    }

    public LiveData<Event<UserInfo>> getRegisterSuccess() {
        return registerSuccess;
    }

    /**
     * 发起注册
     */
    public void register(
            String account,
            String nickname,
            String password,
            String confirmPassword
    ) {
        // 防止重复请求
        if (requestRunning) {
            return;
        }

        // 账号去除首尾空格
        account = account == null ? "" : account.trim();

        nickname = nickname == null ? "" : nickname.trim();

        password = password == null ? "" : password;

        confirmPassword = confirmPassword == null
                ? ""
                : confirmPassword;

        // 1. 校验账号
        if (account.isEmpty()) {
            showError("请输入账号");
            return;
        }

        if (!ACCOUNT_PATTERN.matcher(account).matches()) {
            showError("账号需要为4-64位，只能使用字母、数字和 . _ - @");
            return;
        }

        // 2. 校验密码
        if (password.isEmpty()) {
            showError("请输入密码");
            return;
        }

        if (password.length() < 6 || password.length() > 64) {
            showError("密码长度需要在6-64位之间");
            return;
        }

        // 3. 校验确认密码
        if (!password.equals(confirmPassword)) {
            showError("两次输入的密码不一致");
            return;
        }

        requestRunning = true;

        // 通知页面进入加载状态
        uiState.setValue(RegisterUiState.loading());

        // 调用 Repository
        authRepository.register(
                account,
                password,
                nickname,
                new ApiCallback<UserInfo>() {
                    @Override
                    public void onSuccess(UserInfo userInfo) {

                        requestRunning = false;

                        // 清除加载状态
                        uiState.setValue(RegisterUiState.idle());

                        // 发送一次性注册成功事件
                        registerSuccess.setValue(
                                new Event<>(userInfo)
                        );
                    }

                    @Override
                    public void onError(ApiException error) {

                        requestRunning = false;

                        uiState.setValue(
                                RegisterUiState.error(
                                        getErrorMessage(error)
                                )
                        );
                    }
                }
        );
    }

    private void showError(String message) {
        uiState.setValue(RegisterUiState.error(message));
    }

    /**
     * 转换后端错误信息
     */
    private String getErrorMessage(ApiException error) {

        if (error.getApiCode() != null) {

            // 账号已存在
            if (error.getApiCode() == 40901) {
                return "该账号已经被注册，请更换账号";
            }

            // 参数校验失败
            if (error.getApiCode() == 42201) {
                return "注册信息不符合要求，请检查输入内容";
            }
        }

        String message = error.getMessage();

        if (message == null || message.trim().isEmpty()) {
            return "注册失败，请稍后重试";
        }

        return message;
    }
}