package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

public class UserInfo {
    @SerializedName("id")
    private int id;
    @SerializedName("account")
    private String account;
    @SerializedName("nickname")
    private String nickname;
    @SerializedName("avatar")
    private String avatar;

    public int getId() { return id; }
    public String getAccount() { return account; }
    public String getNickname() { return nickname; }
    public String getAvatar() { return avatar; }
}
