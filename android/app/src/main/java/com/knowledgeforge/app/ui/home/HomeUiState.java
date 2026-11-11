package com.knowledgeforge.app.ui.home;

import com.knowledgeforge.app.network.model.HomeDashboardData;

public class HomeUiState {

    private final boolean loading;
    private final HomeDashboardData data;

    private HomeUiState(boolean loading, HomeDashboardData data) {
        this.loading = loading;
        this.data = data;
    }

    public static HomeUiState loading() {
        return new HomeUiState(true, null);
    }

    public static HomeUiState content(HomeDashboardData data) {
        return new HomeUiState(false, data);
    }

    public boolean isLoading() {
        return loading;
    }

    public HomeDashboardData getData() {
        return data;
    }
}
