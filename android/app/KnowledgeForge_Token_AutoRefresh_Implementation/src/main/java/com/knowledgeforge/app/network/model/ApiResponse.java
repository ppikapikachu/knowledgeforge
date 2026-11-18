package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/** 后端统一响应：{ "code": 0, "message": "success", "data": ... } */
public class ApiResponse<T> {
    @SerializedName("code")
    private Integer code;

    @SerializedName("message")
    private String message;

    @SerializedName("data")
    private T data;

    public Integer getCode() {
        return code;
    }

    public String getMessage() {
        return message;
    }

    public T getData() {
        return data;
    }
}
