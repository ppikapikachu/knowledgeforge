package com.knowledgeforge.app.network;

import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.annotations.SerializedName;
import com.knowledgeforge.app.network.callback.ApiCallback;
import com.knowledgeforge.app.network.model.ApiException;
import com.knowledgeforge.app.network.model.ApiResponse;

import java.io.IOException;

import okhttp3.ResponseBody;
import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

/** 统一解析 HTTP 层和业务层结果。Retrofit enqueue 的回调在 Android 主线程执行。 */
public final class ApiCallExecutor {
    private static final Gson GSON = new Gson();

    private ApiCallExecutor() {}

    public static <T> void enqueue(Call<ApiResponse<T>> call, ApiCallback<T> callback) {
        call.enqueue(new Callback<ApiResponse<T>>() {
            @Override
            public void onResponse(Call<ApiResponse<T>> call,
                                   Response<ApiResponse<T>> response) {
                if (!response.isSuccessful()) {
                    callback.onError(parseHttpError(response.code(), response.errorBody()));
                    return;
                }

                ApiResponse<T> body = response.body();
                if (body == null) {
                    callback.onError(new ApiException(response.code(), null,
                            "服务器返回内容为空", null));
                    return;
                }

                if (body.getCode() == null) {
                    callback.onError(new ApiException(response.code(), null,
                            "服务器响应格式不正确（缺少 code）", null));
                    return;
                }

                if (body.getCode() != 0) {
                    callback.onError(new ApiException(response.code(), body.getCode(),
                            body.getMessage(), null));
                    return;
                }

                callback.onSuccess(body.getData());
            }

            @Override
            public void onFailure(Call<ApiResponse<T>> call, Throwable t) {
                if (call.isCanceled()) {
                    callback.onError(new ApiException(-1, null, "请求已取消", null, t));
                } else {
                    callback.onError(new ApiException(-1, null,
                            "网络请求失败，请检查网络连接", null, t));
                }
            }
        });
    }

    private static ApiException parseHttpError(int httpCode, ResponseBody errorBody) {
        if (errorBody != null) {
            try {
                String raw = errorBody.string();
                if (raw != null && !raw.trim().isEmpty()) {
                    ApiErrorEnvelope envelope = GSON.fromJson(raw, ApiErrorEnvelope.class);
                    if (envelope != null) {
                        return new ApiException(httpCode, envelope.code,
                                envelope.message == null ? "请求失败" : envelope.message,
                                envelope.data);
                    }
                }
            } catch (Exception ignored) {
                // 非 JSON 错误体时，回退到 HTTP 状态码提示。
            }
        }
        return new ApiException(httpCode, null,
                "HTTP 请求失败，状态码：" + httpCode, null);
    }

    private static class ApiErrorEnvelope {
        @SerializedName("code") Integer code;
        @SerializedName("message") String message;
        @SerializedName("data") JsonElement data;
    }
}
