package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 注册请求体（对应后端 schema UserRegisterRequest，接口 POST /api/v1/users/register）。
 * account / password 必填；nickname / avatar 可选。
 * 账号由服务端规范化（去空格+小写），重复注册返回业务错误 40901。
 */
public class UserRegisterRequest {

    /** 登录账号（必填，4-64 字符，仅允许字母/数字/._-@，服务端规范化为小写）。 */
    @SerializedName("account")
    private String account;

    /** 登录密码（必填，6-64 字符，服务端仅存 bcrypt 哈希，不会明文落库）。 */
    @SerializedName("password")
    private String password;

    /** 昵称（可空，展示用）。 */
    @SerializedName("nickname")
    private String nickname;

    /** 头像 URL（可空）。 */
    @SerializedName("avatar")
    private String avatar;

    public UserRegisterRequest(String account, String password) {
        this.account = account;
        this.password = password;
    }

    public void setNickname(String nickname) {
        this.nickname = nickname;
    }

    public void setAvatar(String avatar) {
        this.avatar = avatar;
    }

    public String getAccount() {
        return account;
    }

    public String getPassword() {
        return password;
    }

    public String getNickname() {
        return nickname;
    }

    public String getAvatar() {
        return avatar;
    }
}
