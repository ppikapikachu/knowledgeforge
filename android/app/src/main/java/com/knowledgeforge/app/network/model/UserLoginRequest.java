package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 登录请求体（对应后端 schema UserLoginRequest，接口 POST /api/v1/users/login）。
 * account / password 必填；device_id / device_name 可选（多设备会话管理与展示）。
 * 登录失败时后端统一返回「账号或密码错误」，不暴露账号是否存在。
 */
public class UserLoginRequest {

    /** 登录账号（必填，大小写不敏感，服务端规范化匹配）。 */
    @SerializedName("account")
    private String account;

    /** 登录密码（必填）。 */
    @SerializedName("password")
    private String password;

    /** 设备标识（可空，用于多设备会话管理）。 */
    @SerializedName("device_id")
    private String deviceId;

    /** 设备名称（可空，仅作会话展示）。 */
    @SerializedName("device_name")
    private String deviceName;

    public UserLoginRequest(String account, String password) {
        this.account = account;
        this.password = password;
    }

    public void setDeviceId(String deviceId) {
        this.deviceId = deviceId;
    }

    public void setDeviceName(String deviceName) {
        this.deviceName = deviceName;
    }

    public String getAccount() {
        return account;
    }

    public String getPassword() {
        return password;
    }

    public String getDeviceId() {
        return deviceId;
    }

    public String getDeviceName() {
        return deviceName;
    }
}
