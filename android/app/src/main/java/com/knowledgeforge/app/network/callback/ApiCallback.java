package com.knowledgeforge.app.network.callback;

import com.knowledgeforge.app.network.model.ApiException;

public interface ApiCallback<T> {
    void onSuccess(T data);
    void onError(ApiException error);
}
