package com.knowledgeforge.app.data.repository;

import com.knowledgeforge.app.network.ApiCallExecutor;
import com.knowledgeforge.app.network.api.PracticeApiService;
import com.knowledgeforge.app.network.api.StatisticsApiService;
import com.knowledgeforge.app.network.callback.ApiCallback;
import com.knowledgeforge.app.network.model.ApiException;
import com.knowledgeforge.app.network.model.ApiResponse;
import com.knowledgeforge.app.network.model.AssemblePaperRequest;
import com.knowledgeforge.app.network.model.AssemblePaperResponse;
import com.knowledgeforge.app.network.model.KnowledgePointsResponse;
import com.knowledgeforge.app.network.model.PageResponse;
import com.knowledgeforge.app.network.model.PaperListItem;
import com.knowledgeforge.app.network.model.PracticeLandingData;
import com.knowledgeforge.app.network.model.QuestionBank;
import com.knowledgeforge.app.network.model.SessionListItem;
import com.knowledgeforge.app.network.model.SessionResponse;
import com.knowledgeforge.app.network.model.UserStatisticsResponse;

import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 用户端练习 Repository。
 * 仅复用已有 PracticeApiService / StatisticsApiService，不创建第二套 Retrofit 或 Token 存储。
 */
public class PracticeRepository {

    public interface LandingCallback {
        void onLoaded(PracticeLandingData data);
    }

    private final PracticeApiService practiceApi;
    private final StatisticsApiService statisticsApi;

    public PracticeRepository(PracticeApiService practiceApi,
                              StatisticsApiService statisticsApi) {
        this.practiceApi = practiceApi;
        this.statisticsApi = statisticsApi;
    }

    /** 并行加载练习入口需要的数据，单个接口失败不会丢弃其他成功结果。 */
    public void loadLanding(LandingCallback callback) {
        final PracticeLandingData data = new PracticeLandingData();
        final AtomicInteger pending = new AtomicInteger(4);
        final AtomicBoolean delivered = new AtomicBoolean(false);
        Runnable finishOne = () -> {
            if (pending.decrementAndGet() == 0 && delivered.compareAndSet(false, true)) {
                callback.onLoaded(data);
            }
        };

        ApiCallExecutor.enqueue(practiceApi.getQuestionBanks(1, 100, null),
                new ApiCallback<PageResponse<QuestionBank>>() {
                    @Override public void onSuccess(PageResponse<QuestionBank> result) {
                        data.setQuestionBanks(result == null ? null : result.getItems());
                        finishOne.run();
                    }
                    @Override public void onError(ApiException error) {
                        data.addError(error.getMessage());
                        finishOne.run();
                    }
                });

        ApiCallExecutor.enqueue(practiceApi.getSessions("in_progress", 1, 10),
                new ApiCallback<PageResponse<SessionListItem>>() {
                    @Override public void onSuccess(PageResponse<SessionListItem> result) {
                        data.setActiveSessions(result == null ? null : result.getItems());
                        finishOne.run();
                    }
                    @Override public void onError(ApiException error) {
                        data.addError(error.getMessage());
                        finishOne.run();
                    }
                });

        ApiCallExecutor.enqueue(practiceApi.getPapers(1, 20),
                new ApiCallback<PageResponse<PaperListItem>>() {
                    @Override public void onSuccess(PageResponse<PaperListItem> result) {
                        data.setPapers(result == null ? null : result.getItems());
                        finishOne.run();
                    }
                    @Override public void onError(ApiException error) {
                        data.addError(error.getMessage());
                        finishOne.run();
                    }
                });

        ApiCallExecutor.enqueue(statisticsApi.getMyStatistics(),
                new ApiCallback<UserStatisticsResponse>() {
                    @Override public void onSuccess(UserStatisticsResponse result) {
                        data.setStatistics(result);
                        finishOne.run();
                    }
                    @Override public void onError(ApiException error) {
                        data.addError(error.getMessage());
                        finishOne.run();
                    }
                });
    }

    public void getQuestionBanks(ApiCallback<PageResponse<QuestionBank>> callback) {
        ApiCallExecutor.enqueue(practiceApi.getQuestionBanks(1, 100, null), callback);
    }

    public void getKnowledgePoints(int bankId, ApiCallback<KnowledgePointsResponse> callback) {
        ApiCallExecutor.enqueue(practiceApi.getQuestionBankKnowledgePoints(bankId), callback);
    }

    public void assemblePaper(String idempotencyKey,
                              AssemblePaperRequest request,
                              ApiCallback<AssemblePaperResponse> callback) {
        ApiCallExecutor.enqueue(practiceApi.assemblePaper(idempotencyKey, request), callback);
    }

    public void resumeSession(int sessionId, ApiCallback<SessionResponse> callback) {
        ApiCallExecutor.enqueue(practiceApi.resumeSession(sessionId), callback);
    }
}
