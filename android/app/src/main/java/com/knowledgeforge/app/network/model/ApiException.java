package com.knowledgeforge.app.network.model;

import com.google.gson.JsonElement;

/** 将 HTTP 状态码与后端业务 code 分开保存，避免只看 HTTP 200/400。 */
public class ApiException extends Exception {
    private final int httpCode;
    private final Integer apiCode;
    private final JsonElement errorData;

    public ApiException(int httpCode, Integer apiCode, String message, JsonElement errorData) {
        super(message == null || message.trim().isEmpty() ? "请求失败" : message);
        this.httpCode = httpCode;
        this.apiCode = apiCode;
        this.errorData = errorData;
    }

    public ApiException(int httpCode, Integer apiCode, String message,
                        JsonElement errorData, Throwable cause) {
        super(message == null || message.trim().isEmpty() ? "请求失败" : message, cause);
        this.httpCode = httpCode;
        this.apiCode = apiCode;
        this.errorData = errorData;
    }

    public int getHttpCode() {
        return httpCode;
    }

    public Integer getApiCode() {
        return apiCode;
    }

    public JsonElement getErrorData() {
        return errorData;
    }
}
