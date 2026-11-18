package com.knowledgeforge.app.ui.practice;

import androidx.lifecycle.LiveData;
import androidx.lifecycle.MutableLiveData;
import androidx.lifecycle.ViewModel;

import com.knowledgeforge.app.data.repository.PracticeRepository;

/** 练习入口页状态持有者。 */
public class PracticeLandingViewModel extends ViewModel {
    private final PracticeRepository repository;
    private final MutableLiveData<PracticeLandingUiState> uiState =
            new MutableLiveData<>(PracticeLandingUiState.loading());
    private boolean loaded;
    private boolean loading;
    private int requestVersion;

    public PracticeLandingViewModel(PracticeRepository repository) {
        this.repository = repository;
    }

    public LiveData<PracticeLandingUiState> getUiState() { return uiState; }

    public void loadIfNeeded() {
        if (!loaded && !loading) load();
    }

    public void refresh() {
        if (!loading) load();
    }

    private void load() {
        loading = true;
        final int version = ++requestVersion;
        uiState.setValue(PracticeLandingUiState.loading());
        repository.loadLanding(data -> {
            if (version != requestVersion) return;
            loading = false;
            loaded = true;
            uiState.setValue(PracticeLandingUiState.content(data));
        });
    }
}
