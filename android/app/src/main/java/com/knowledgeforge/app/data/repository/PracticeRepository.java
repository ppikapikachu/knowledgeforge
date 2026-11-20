package com.knowledgeforge.app.data.repository;

import com.knowledgeforge.app.network.ApiCallExecutor;
import com.knowledgeforge.app.network.api.PracticeApiService;
import com.knowledgeforge.app.network.api.StatisticsApiService;
import com.knowledgeforge.app.network.callback.ApiCallback;
import com.knowledgeforge.app.network.model.ApiException;
import com.knowledgeforge.app.network.model.ApiResponse;
import com.knowledgeforge.app.network.model.AssemblePaperRequest;
import com.knowledgeforge.app.network.model.AssemblePaperResponse;
import com.knowledgeforge.app.network.model.DraftSaveRequest;
import com.knowledgeforge.app.network.model.DraftSaveResponse;
import com.knowledgeforge.app.network.model.KnowledgePointsResponse;
import com.knowledgeforge.app.network.model.MarkItemResponse;
import com.knowledgeforge.app.network.model.MarkRequest;
import com.knowledgeforge.app.network.model.PageResponse;
import com.knowledgeforge.app.network.model.PaperListItem;
import com.knowledgeforge.app.network.model.PracticeLandingData;
import com.knowledgeforge.app.network.model.ProgressRequest;
import com.knowledgeforge.app.network.model.ProgressUpdateResponse;
import com.knowledgeforge.app.network.model.QuestionBank;
import com.knowledgeforge.app.network.model.SessionAnswersResponse;
import com.knowledgeforge.app.network.model.SessionDetailResponse;
import com.knowledgeforge.app.network.model.SessionListItem;
import com.knowledgeforge.app.network.model.SessionResponse;
import com.knowledgeforge.app.network.model.SessionResultResponse;
import com.knowledgeforge.app.network.model.SubmitAnswerRequest;
import com.knowledgeforge.app.network.model.SubmitAnswerResponse;
import com.knowledgeforge.app.network.model.UserStatisticsResponse;

import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 用户端练习 Repository。
 *
 * <p>职责：把 ViewModel 需要的练习数据操作转换成对 PracticeApiService 的调用，
 * 并统一交给 ApiCallExecutor 处理响应封套、业务错误和 Token 自动刷新。</p>
 *
 * <p>本类不创建新的 Retrofit/OkHttp 实例，不保存 Activity/Fragment，也不直接操作 View。
 * 页面层只依赖本类，不直接拼接接口地址或处理 ApiResponse。</p>
 */
public class PracticeRepository {

    /** 练习入口页四组数据全部完成后的回调。 */
    public interface LandingCallback {
        void onLoaded(PracticeLandingData data);
    }

    private final PracticeApiService practiceApi;
    private final StatisticsApiService statisticsApi;

    /**
     * 创建练习数据仓库。
     *
     * @param practiceApi   项目已有的练习接口声明
     * @param statisticsApi 项目已有的用户统计接口声明
     */
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

    /**
     * 分页获取当前用户的练习会话记录。
     * status 为 null 时查全部；否则传 in_progress/completed/abandoned。
     */
    public void getSessions(String status, int page, int pageSize,
                            ApiCallback<PageResponse<SessionListItem>> callback) {
        ApiCallExecutor.enqueue(practiceApi.getSessions(status, page, pageSize), callback);
    }

    /** 分页获取本人试卷，用于把 session.paper_id 映射为页面显示的试卷标题。 */
    public void getPapers(int page, int pageSize,
                          ApiCallback<PageResponse<PaperListItem>> callback) {
        ApiCallExecutor.enqueue(practiceApi.getPapers(page, pageSize), callback);
    }

    /** 获取个人统计摘要，供记录页顶部显示总练习次数、总答题数和平均正确率。 */
    public void getMyStatistics(ApiCallback<UserStatisticsResponse> callback) {
        ApiCallExecutor.enqueue(statisticsApi.getMyStatistics(), callback);
    }

    /** 获取开放练习题库，供组卷页面使用。 */
    public void getQuestionBanks(ApiCallback<PageResponse<QuestionBank>> callback) {
        ApiCallExecutor.enqueue(practiceApi.getQuestionBanks(1, 100, null), callback);
    }

    /** 获取指定题库中可供组卷筛选的知识点。 */
    public void getKnowledgePoints(int bankId, ApiCallback<KnowledgePointsResponse> callback) {
        ApiCallExecutor.enqueue(practiceApi.getQuestionBankKnowledgePoints(bankId), callback);
    }

    /** 创建试卷快照并由后端自动创建首次练习会话。 */
    public void assemblePaper(String idempotencyKey,
                              AssemblePaperRequest request,
                              ApiCallback<AssemblePaperResponse> callback) {
        ApiCallExecutor.enqueue(practiceApi.assemblePaper(idempotencyKey, request), callback);
    }

    /** 恢复一个正在进行的会话；用于练习入口的“继续练习”。 */
    public void resumeSession(int sessionId, ApiCallback<SessionResponse> callback) {
        ApiCallExecutor.enqueue(practiceApi.resumeSession(sessionId), callback);
    }

    /** 获取会话详情：题目快照、草稿、标记和答题状态都从这里读取。 */
    public void getSessionDetail(int sessionId, ApiCallback<SessionDetailResponse> callback) {
        ApiCallExecutor.enqueue(practiceApi.getSessionDetail(sessionId), callback);
    }

    /** 提交当前题答案，由后端按照试卷快照判分。 */
    public void submitAnswer(int sessionId, int paperItemId,
                             SubmitAnswerRequest request,
                             ApiCallback<SubmitAnswerResponse> callback) {
        ApiCallExecutor.enqueue(practiceApi.submitAnswer(sessionId, paperItemId, request), callback);
    }

    /** 保存当前题草稿；不会判分，也不会计入已答题数量。 */
    public void saveDraft(int sessionId, int paperItemId,
                          DraftSaveRequest request,
                          ApiCallback<DraftSaveResponse> callback) {
        ApiCallExecutor.enqueue(practiceApi.saveDraft(sessionId, paperItemId, request), callback);
    }

    /** 标记或取消标记当前题。 */
    public void markItem(int sessionId, int paperItemId,
                         MarkRequest request,
                         ApiCallback<MarkItemResponse> callback) {
        ApiCallExecutor.enqueue(practiceApi.markItem(sessionId, paperItemId, request), callback);
    }

    /** 更新当前题序，供下次恢复练习时定位。 */
    public void updateProgress(int sessionId, int currentOrder,
                               ApiCallback<ProgressUpdateResponse> callback) {
        ApiCallExecutor.enqueue(practiceApi.updateProgress(
                sessionId, new ProgressRequest(currentOrder)), callback);
    }

    /** 完成本次练习会话，后端会将会话转为 completed。 */
    public void completeSession(int sessionId, ApiCallback<SessionResponse> callback) {
        ApiCallExecutor.enqueue(practiceApi.completeSession(sessionId), callback);
    }

    /** 获取整卷结果和答案解析；通常在 completeSession 成功后调用。 */
    public void getSessionResult(int sessionId, ApiCallback<SessionResultResponse> callback) {
        ApiCallExecutor.enqueue(practiceApi.getSessionResult(sessionId), callback);
    }

    /** 获取会话中每次提交的答题记录，供后续记录页或详细回顾使用。 */
    public void getSessionAnswers(int sessionId, ApiCallback<SessionAnswersResponse> callback) {
        ApiCallExecutor.enqueue(practiceApi.getSessionAnswers(sessionId), callback);
    }

    /** 对已存在的试卷新建一轮练习会话。 */
    public void createPaperSession(int paperId, ApiCallback<SessionResponse> callback) {
        ApiCallExecutor.enqueue(practiceApi.createPaperSession(paperId), callback);
    }
}
