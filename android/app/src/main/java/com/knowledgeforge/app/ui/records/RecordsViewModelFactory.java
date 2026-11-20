package com.knowledgeforge.app.ui.records;

import androidx.annotation.NonNull;
import androidx.lifecycle.ViewModel;
import androidx.lifecycle.ViewModelProvider;

import com.knowledgeforge.app.data.repository.PracticeRepository;

/** 为 RecordsViewModel 注入项目现有 PracticeRepository 的工厂。 */
public class RecordsViewModelFactory implements ViewModelProvider.Factory {

    /** 被注入的练习 Repository。 */
    private final PracticeRepository repository;

    public RecordsViewModelFactory(PracticeRepository repository) {
        this.repository = repository;
    }

    @NonNull
    @Override
    @SuppressWarnings("unchecked")
    public <T extends ViewModel> T create(@NonNull Class<T> modelClass) {
        if (modelClass.isAssignableFrom(RecordsViewModel.class)) {
            return (T) new RecordsViewModel(repository);
        }
        throw new IllegalArgumentException("Unknown ViewModel class: " + modelClass.getName());
    }
}
