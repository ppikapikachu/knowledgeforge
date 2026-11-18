package com.knowledgeforge.app.ui.practice;

import androidx.annotation.NonNull;
import androidx.lifecycle.ViewModel;
import androidx.lifecycle.ViewModelProvider;

import com.knowledgeforge.app.data.repository.PracticeRepository;

public class PracticeLandingViewModelFactory implements ViewModelProvider.Factory {
    private final PracticeRepository repository;

    public PracticeLandingViewModelFactory(PracticeRepository repository) {
        this.repository = repository;
    }

    @NonNull
    @Override
    @SuppressWarnings("unchecked")
    public <T extends ViewModel> T create(@NonNull Class<T> modelClass) {
        if (modelClass.isAssignableFrom(PracticeLandingViewModel.class)) {
            return (T) new PracticeLandingViewModel(repository);
        }
        throw new IllegalArgumentException("Unknown ViewModel class");
    }
}
