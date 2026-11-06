package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 退出登录请求体（对应后端 schema UserLogoutRequest，接口 POST /api/v1/users/logout）。
 * 只撤销该 refresh_token 对应的会话，不影响其他设备登录；
 * 接口响应的 data 恒为 null（成功 message=已退出登录）。
 */
public class UserLogoutRequest {

    /** 要撤销的刷新令牌（必填，仅撤销该令牌对应会话）。 */
    @SerializedName("refresh_token")
    private String refreshToken;

    public UserLogoutRequest(String refreshToken) {
        this.refreshToken = refreshToken;
    }

    public String getRefreshToken() {
        return refreshToken;
    }
}
