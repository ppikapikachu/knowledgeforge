# KnowledgeForge Token 自动刷新与登录失效处理

本更新以用户最新上传的 `src(3).zip` 为基础。只修改认证网络链路，没有调整页面布局、练习业务、导航图或其他 Fragment。

## 本次文件变更

### 新增

- `src/main/java/com/knowledgeforge/app/network/auth/TokenRefreshManager.java`
  - 统一处理 Access Token 失效后的 Refresh Token 换新。
  - 同一个 Refresh Token 会话并发遇到 40101 时只执行一次刷新，其他请求异步等待结果。
  - 刷新成功后同时保存新的 Access Token 和 Refresh Token。
  - 只有服务端明确返回业务码 `40101` 才清除本地凭证并触发登录失效事件。
  - 网络错误、超时、5xx、响应格式错误不会清空本地凭证。
  - 不使用 `wait()`/`sleep()` 阻塞线程。

### 修改

- `network/ApiCallExecutor.java`
  - 同时识别 HTTP 非 2xx 错误封套和 HTTP 200 中的业务错误。
  - 仅对带 Bearer Token 的受保护接口 40101 启动刷新。
  - 登录、注册、刷新、退出登录接口不触发自动刷新。
  - 刷新成功后 clone 原 Retrofit Call，并且只重试一次。
- `network/ApiClient.java`
  - 使用现有 `UserApiService` 和唯一的 `TokenStorage` 创建一个 `TokenRefreshManager`。
  - 在网络请求开始前注入 `ApiCallExecutor`。
- `data/local/TokenStorage.java`
  - 增加 Refresh Token 比较后替换令牌对、条件清除会话的接口。
- `data/local/SharedPreferencesTokenStorage.java`
  - Access Token、Refresh Token、类型和过期时间继续通过一个 Editor 更新。
  - 新增基于旧 Refresh Token 的条件更新/清除，防止迟到响应误覆盖或删除新会话。
- `data/repository/AuthRepository.java`
  - 注册成功保存令牌后也调用 `AuthSessionEventManager.markAuthenticated()`；登录成功原本已有该调用，予以保留。

## 复用的现有文件

- `network/api/UserApiService.java`：继续使用已有 `POST /api/v1/users/refresh`。
- `network/model/UserRefreshRequest.java`：继续传 `refresh_token`。
- `network/model/AuthTokenData.java`：继续接收完整令牌对。
- `network/auth/AuthInterceptor.java`：继续自动附加 Access Token；其现有路径规则已排除 login/register/refresh。
- `network/auth/AuthSessionEventManager.java`：继续负责登录失效事件与去重。
- `MainActivity.java`：上传版本已存在事件监听，收到失效事件后清除会话并清空返回栈跳转 LoginActivity，本次无需修改。

## 实际行为

1. 普通受保护 API 返回业务码 `40101`。
2. ApiCallExecutor 从实际 HTTP 请求中读取本次使用的 Bearer Access Token。
3. TokenRefreshManager 检查本地 Access Token 是否已被其他请求更新。
4. 若没有更新，则使用 Refresh Token 请求 `/api/v1/users/refresh`。
5. 成功时比较旧 Refresh Token 后一次性保存新令牌对，并唤醒等待请求。
6. ApiCallExecutor 使用新 Token 重试原请求一次；重试再次 40101 时不再刷新。
7. Refresh Token 明确返回 `40101` 时，条件清除该旧会话并通知 AuthSessionEventManager，MainActivity 跳转登录页。
8. 刷新请求网络失败或服务端 5xx 时保留本地令牌，不强制跳转登录；当前请求收到刷新错误，后续请求仍可再次尝试刷新。

## 合并方法

将 ZIP 中 `src/` 合并到 Android 项目的 `app/src/`，保留当前工程中未涉及的文件。

## 建议联调测试

- Access Token 有效：普通请求直接成功，不触发刷新。
- Access Token 过期、Refresh Token 有效：只刷新一次，原请求自动重试成功。
- 多个接口同时返回 40101：同一会话仅有一个 refresh 请求。
- 登录接口账号密码错误返回 40101：只展示登录错误，不触发 refresh。
- Refresh Token 返回 40101：只清除失效会话，跳转登录页一次。
- Refresh 请求断网/超时/5xx：不清除 Token，不强制跳登录页。
- Refresh 成功后旧 Refresh Token 已轮换：下次刷新必须使用新 Token。
- 刷新响应迟到且用户已经重新登录：旧响应不能覆盖新令牌对。
- 刷新后重试仍返回 40101：不会无限刷新或无限重试。

## 验证边界

上传的 `src(3).zip` 不包含 `build.gradle`、Gradle Wrapper 等完整构建配置，因此不能在此执行真实 Android Gradle Build 或设备联调。本次已对核心变更类和 ApiClient 使用依赖桩执行 `javac` 编译检查；这不能替代 Android Studio 的完整构建和真实后端测试。
