package com.knowledgeforge.app.network.callback;

import com.knowledgeforge.app.network.model.ApiException;

/**
 * 网络请求统一回调（配合 ApiCallExecutor.enqueue 使用）。
 * 成功仅指后端业务码 code=0（HTTP 2xx 且封套成功）；HTTP 错误与业务错误
 * （code!=0，如 40001/40101/40401）统一走 onError，异常信息见 ApiException。
 */
public interface ApiCallback<T> {
    /** 业务成功（code=0），data 为封套内的业务数据（可能为 null，如 logout）。 */
    void onSuccess(T data);

    /** 请求失败：网络/HTTP 错误或业务码错误，统一回调 ApiException。 */
    void onError(ApiException error);
}
