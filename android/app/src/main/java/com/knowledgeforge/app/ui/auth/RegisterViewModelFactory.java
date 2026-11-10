package com.knowledgeforge.app.ui.auth;

import androidx.annotation.NonNull;
import androidx.lifecycle.ViewModel;
import androidx.lifecycle.ViewModelProvider;

import com.knowledgeforge.app.data.repository.AuthRepository;

public class RegisterViewModelFactory implements ViewModelProvider.Factory {

    private final AuthRepository authRepository;

    public RegisterViewModelFactory(AuthRepository authRepository) {
        this.authRepository = authRepository;
    }

    @NonNull
    @Override
    @SuppressWarnings("unchecked")
    public <T extends ViewModel> T create(@NonNull Class<T> modelClass) {

        if (modelClass.isAssignableFrom(RegisterViewModel.class)) {
            return (T) new RegisterViewModel(authRepository);
        }

        throw new IllegalArgumentException("Unknown ViewModel class");
    }
}