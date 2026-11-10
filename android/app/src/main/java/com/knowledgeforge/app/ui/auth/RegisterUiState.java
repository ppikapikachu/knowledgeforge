package com.knowledgeforge.app.ui.auth;


public class RegisterUiState {

    private final boolean loading;
    private final String errorMessage;

    public RegisterUiState(boolean loading, String errorMessage) {
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
        return errorMessage != null && !errorMessage.isEmpty();
    }

    public static RegisterUiState idle() {
        return new RegisterUiState(false, null);
    }

    public static RegisterUiState loading() {
        return new RegisterUiState(true, null);
    }

    public static RegisterUiState error(String message) {
        return new RegisterUiState(false, message);
    }
}