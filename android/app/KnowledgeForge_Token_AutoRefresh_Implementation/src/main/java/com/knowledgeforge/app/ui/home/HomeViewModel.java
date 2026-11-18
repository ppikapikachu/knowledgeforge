package com.knowledgeforge.app.ui.home;

import androidx.lifecycle.LiveData;
import androidx.lifecycle.MutableLiveData;
import androidx.lifecycle.ViewModel;

import com.knowledgeforge.app.network.model.HomeDashboardData;
import com.knowledgeforge.app.data.repository.HomeRepository;

/**
 * 首页状态持有者。ViewModel 不直接持有 View，也不操作 TextView/Button。
 */
public class HomeViewModel extends ViewModel {

    private final HomeRepository repository;
    private final MutableLiveData<HomeUiState> uiState =
            new MutableLiveData<>(HomeUiState.loading());

    private boolean loaded;
    private boolean loading;
    private int requestVersion;

    public HomeViewModel(HomeRepository repository) {
        this.repository = repository;
    }

    public LiveData<HomeUiState> getUiState() {
        return uiState;
    }

    public void loadIfNeeded() {
        if (loaded || loading) {
            return;
        }
        load();
    }

    public void refresh() {
        if (loading) {
            return;
        }
        load();
    }

    private void load() {
        loading = true;
        final int version = ++requestVersion;
        uiState.setValue(HomeUiState.loading());

        repository.loadDashboard(data -> {
            // 忽略较早请求的迟到响应，避免刷新竞态覆盖新数据。
            if (version != requestVersion) {
                return;
            }
            loading = false;
            loaded = true;
            uiState.setValue(HomeUiState.content(data));
        });
    }
}
