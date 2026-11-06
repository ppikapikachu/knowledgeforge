package com.knowledgeforge.app.network;

/**
 * 网络层配置：后端服务地址等全局常量。
 * 目前只有 BASE_URL 一项；各接口路径在 api/ 下的接口声明中以相对路径给出。
 */
public final class ApiConfig {
    private ApiConfig() {}

    // 示例：Android 模拟器访问开发电脑本机 FastAPI。
    // 真机请改成开发电脑局域网 IP；服务器环境请改成实际域名/IP。
    // URL 必须以 / 结尾。
    public static final String BASE_URL = "http://10.0.2.2:8000/";
}
