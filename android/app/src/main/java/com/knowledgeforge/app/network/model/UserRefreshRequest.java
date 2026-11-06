package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 刷新令牌请求体（对应后端 schema UserRefreshRequest，接口 POST /api/v1/users/refresh）。
 * 采用令牌轮换机制：刷新成功后旧 refresh_token 立即作废，客户端必须同时替换
 * access_token 与 refresh_token；旧票重放会返回业务错误 40101。
 */
public class UserRefreshRequest {

    /** 刷新令牌（必填，登录/注册时下发的长期凭证）。 */
    @SerializedName("refresh_token")
    private String refreshToken;

    public UserRefreshRequest(String refreshToken) {
        this.refreshToken = refreshToken;
    }

    public String getRefreshToken() {
        return refreshToken;
    }
}
