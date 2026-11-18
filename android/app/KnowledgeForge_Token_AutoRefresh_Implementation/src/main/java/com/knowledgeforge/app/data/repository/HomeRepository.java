package com.knowledgeforge.app.data.repository;

import com.knowledgeforge.app.network.ApiCallExecutor;
import com.knowledgeforge.app.network.api.PracticeApiService;
import com.knowledgeforge.app.network.api.UserApiService;
import com.knowledgeforge.app.network.callback.ApiCallback;
import com.knowledgeforge.app.network.model.ApiException;
import com.knowledgeforge.app.network.model.ApiResponse;
import com.knowledgeforge.app.network.model.HomeDashboardData;
import com.knowledgeforge.app.network.model.PageResponse;
import com.knowledgeforge.app.network.model.PaperListItem;
import com.knowledgeforge.app.network.model.QuestionBank;
import com.knowledgeforge.app.network.model.SessionListItem;
import com.knowledgeforge.app.network.model.UserInfo;

import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

import retrofit2.Call;

/**
 * 首页数据仓库。
 *
 * 只聚合已有 API，不在此处写死题库、练习进度或用户名称。
 * 当前并发请求：当前用户资料、开放题库、进行中的会话、最近试卷。
 */
public class HomeRepository {

    public interface DashboardCallback {
        void onLoaded(HomeDashboardData data);
    }

    private final UserApiService userApiService;
    private final PracticeApiService practiceApiService;

    public HomeRepository(UserApiService userApiService,
                          PracticeApiService practiceApiService) {
        this.userApiService = userApiService;
        this.practiceApiService = practiceApiService;
    }

    public void loadDashboard(DashboardCallback callback) {
        final HomeDashboardData data = new HomeDashboardData();
        final AtomicInteger pending = new AtomicInteger(4); // 所有请求完成的判定
        final AtomicBoolean delivered = new AtomicBoolean(false);

        Runnable finishOne = () -> {
            if (pending.decrementAndGet() == 0 && delivered.compareAndSet(false, true)) {
                callback.onLoaded(data);
            }
        };

        // 1. 当前登录用户资料：GET /users/me
        ApiCallExecutor.enqueue(userApiService.getCurrentUser(),
                new ApiCallback<UserInfo>() {
                    @Override
                    public void onSuccess(UserInfo result) {
                        data.setUser(result);
                        finishOne.run();
                    }

                    @Override
                    public void onError(ApiException error) {
                        data.addError(error.getMessage());
                        finishOne.run();
                    }
                });

        // 2. 开放题库：GET /practice/question-banks
        ApiCallExecutor.enqueue(practiceApiService.getQuestionBanks(1, 4, null),
                new ApiCallback<PageResponse<QuestionBank>>() {
                    @Override
                    public void onSuccess(PageResponse<QuestionBank> result) {
                        data.setQuestionBanks(result == null ? null : result.getItems());
                        finishOne.run();
                    }

                    @Override
                    public void onError(ApiException error) {
                        data.addError(error.getMessage());
                        finishOne.run();
                    }
                });

        // 3. 进行中的练习：GET /practice/sessions?status=in_progress
        ApiCallExecutor.enqueue(practiceApiService.getSessions("in_progress", 1, 5),
                new ApiCallback<PageResponse<SessionListItem>>() {
                    @Override
                    public void onSuccess(PageResponse<SessionListItem> result) {
                        data.setActiveSessions(result == null ? null : result.getItems());
                        finishOne.run();
                    }

                    @Override
                    public void onError(ApiException error) {
                        data.addError(error.getMessage());
                        finishOne.run();
                    }
                });

        // 4. 最近试卷：GET /practice/papers
        ApiCallExecutor.enqueue(practiceApiService.getPapers(1, 5),
                new ApiCallback<PageResponse<PaperListItem>>() {
                    @Override
                    public void onSuccess(PageResponse<PaperListItem> result) {
                        data.setRecentPapers(result == null ? null : result.getItems());
                        finishOne.run();
                    }

                    @Override
                    public void onError(ApiException error) {
                        data.addError(error.getMessage());
                        finishOne.run();
                    }
                });
    }
}
