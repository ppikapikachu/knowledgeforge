package com.knowledgeforge.app.ui.login;

public class LoginUiState {

    private final boolean loading;

    private final String errorMessage;

    public LoginUiState(boolean loading, String errorMessage) {
        this.loading = loading;
        this.errorMessage = errorMessage;
    }

    public boolean isLoading() {
        return loading;
    }

    public String getErrorMessage() {
        return errorMessage;
    }

    public boolean hasError() {
        return errorMessage != null
                && !errorMessage.trim().isEmpty();
    }

    public static LoginUiState idle() {
        return new LoginUiState(false, null);
    }

    public static LoginUiState loading() {
        return new LoginUiState(true, null);
    }

    public static LoginUiState error(String message) {
        return new LoginUiState(false, message);
    }
}