package com.knowledgeforge.app.ui.login;

import androidx.annotation.NonNull;
import androidx.lifecycle.ViewModel;
import androidx.lifecycle.ViewModelProvider;

import com.knowledgeforge.app.data.repository.AuthRepository;

/**
 * 直接 new，它就和普通的 Java 对象没区别了，屏幕旋转时数据会丢失，而且你没法方便地往里注入 Repository 或者 Context
 * 所以创建 Factory。
 */
public class LoginViewModelFactory implements ViewModelProvider.Factory {

    private final AuthRepository authRepository;

    public LoginViewModelFactory(AuthRepository authRepository) {
        this.authRepository = authRepository;
    }

    @NonNull
    @Override
    @SuppressWarnings("unchecked")
    public <T extends ViewModel> T create(
            @NonNull Class<T> modelClass
    ) {

        if (modelClass.isAssignableFrom(LoginViewModel.class)) {
            return (T) new LoginViewModel(authRepository);
        }

        throw new IllegalArgumentException(
                "Unknown ViewModel class: " + modelClass.getName()
        );
    }
}