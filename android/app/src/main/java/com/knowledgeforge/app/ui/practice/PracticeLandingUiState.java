package com.knowledgeforge.app.ui.practice;

import com.knowledgeforge.app.network.model.PracticeLandingData;

public class PracticeLandingUiState {
    private final boolean loading;
    private final PracticeLandingData data;
    private final String errorMessage;

    private PracticeLandingUiState(boolean loading, PracticeLandingData data, String errorMessage) {
        this.loading = loading;
        this.data = data;
        this.errorMessage = errorMessage;
    }

    public static PracticeLandingUiState loading() {
        return new PracticeLandingUiState(true, null, null);
    }

    public static PracticeLandingUiState content(PracticeLandingData data) {
        return new PracticeLandingUiState(false, data, null);
    }

    public static PracticeLandingUiState error(String message) {
        return new PracticeLandingUiState(false, null, message);
    }

    public boolean isLoading() { return loading; }
    public PracticeLandingData getData() { return data; }
    public String getErrorMessage() { return errorMessage; }
}
