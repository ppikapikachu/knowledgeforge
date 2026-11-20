package com.knowledgeforge.app.ui.records;

import androidx.lifecycle.LiveData;
import androidx.lifecycle.MutableLiveData;
import androidx.lifecycle.ViewModel;

import com.knowledgeforge.app.data.repository.PracticeRepository;
import com.knowledgeforge.app.network.callback.ApiCallback;
import com.knowledgeforge.app.network.model.ApiException;
import com.knowledgeforge.app.network.model.PageResponse;
import com.knowledgeforge.app.network.model.PaperListItem;
import com.knowledgeforge.app.network.model.SessionListItem;
import com.knowledgeforge.app.network.model.UserAnswerSummary;
import com.knowledgeforge.app.network.model.UserPracticeSummary;
import com.knowledgeforge.app.network.model.UserStatisticsResponse;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 练习记录页 ViewModel。
 * 负责会话分页、状态筛选、试卷标题映射和顶部统计数据整合；不持有 Activity 或 View。
 */
public class RecordsViewModel extends ViewModel {

    /** 每页请求数量，与后端分页规则一致（最大 100）。 */
    private static final int PAGE_SIZE = 20;
    /** 练习数据仓库，复用项目当前 Retrofit/Token/ApiCallExecutor 配置。 */
    private final PracticeRepository repository;
    /** 页面唯一状态出口。 */
    private final MutableLiveData<RecordsUiState> uiState =
            new MutableLiveData<>(RecordsUiState.initial());

    /** 已累计加载的会话，按后端返回顺序展示。 */
    private final List<SessionListItem> sessions = new ArrayList<>();
    /** 试卷标题缓存；会话接口只返回 paper_id，因此需要通过试卷列表补充标题。 */
    private final Map<Integer, String> paperTitles = new HashMap<>();

    /** 当前筛选状态；null 表示全部。 */
    private String selectedStatus;
    /** 当前已成功加载的页码。 */
    private int currentPage;
    /** 服务端匹配当前筛选条件的记录总数。 */
    private int totalRecords;
    /** 是否还存在下一页。 */
    private boolean hasMore = true;
    /** 当前是否正在请求第一页。 */
    private boolean loading;
    /** 当前是否正在请求更多页。 */
    private boolean loadingMore;
    /** 顶部总练习次数。 */
    private int totalPracticeCount;
    /** 顶部总答题数（至少答过一次的不同题目数量）。 */
    private int totalAnsweredQuestions;
    /** 顶部平均正确率；样本不足或接口未给数值时为 null。 */
    private Double averageAccuracy;
    /** 最近一次刷新标识，避免旧筛选请求覆盖新筛选结果。 */
    private int requestVersion;
    /** 最近一次请求错误。 */
    private String errorMessage;
    /** 是否已经执行过首次刷新，避免 ViewModel 复用时无意义重载。 */
    private boolean firstLoaded;

    public RecordsViewModel(PracticeRepository repository) {
        this.repository = repository;
    }

    /** 暴露只读 LiveData 给 Fragment 观察。 */
    public LiveData<RecordsUiState> getUiState() {
        return uiState;
    }

    /** 首次进入时加载数据；页面重建但 ViewModel 仍存在时保留现有状态。 */
    public void loadIfNeeded() {
        if (!firstLoaded && !loading) {
            refresh();
        }
    }

    /** 下拉/点击刷新时清空当前页并重新请求统计、试卷标题和会话列表。 */
    public void refresh() {
        // 即使上一轮还在加载，也允许启动新筛选；requestVersion 会让旧回调失效。
        final int version = ++requestVersion;
        firstLoaded = true;
        loading = true;
        loadingMore = false;
        currentPage = 0;
        totalRecords = 0;
        hasMore = true;
        errorMessage = null;
        sessions.clear();
        paperTitles.clear();
        publish();

        // 试卷列表只负责补充标题；其失败不影响会话记录本身展示。
        repository.getPapers(1, 100, new ApiCallback<PageResponse<PaperListItem>>() {
            @Override
            public void onSuccess(PageResponse<PaperListItem> result) {
                if (version != requestVersion) return;
                paperTitles.clear();
                if (result != null && result.getItems() != null) {
                    for (PaperListItem paper : result.getItems()) {
                        if (paper != null && paper.getPaperId() > 0
                                && paper.getTitle() != null && !paper.getTitle().trim().isEmpty()) {
                            paperTitles.put(paper.getPaperId(), paper.getTitle().trim());
                        }
                    }
                }
                publish();
            }

            @Override
            public void onError(ApiException error) {
                // 标题接口失败时会在列表中显示“试卷 #ID”，不能阻断会话列表。
                if (version == requestVersion) publish();
            }
        });

        // 顶部统计使用后端用户统计接口的权威聚合值，不在客户端累加当前页推测。
        repository.getMyStatistics(new ApiCallback<UserStatisticsResponse>() {
            @Override
            public void onSuccess(UserStatisticsResponse result) {
                if (version != requestVersion) return;
                applyStatistics(result);
                publish();
            }

            @Override
            public void onError(ApiException error) {
                // 统计接口失败时保留占位值，列表仍然可以正常使用。
                if (version == requestVersion) publish();
            }
        });

        loadPage(version, 1, true);
    }

    /** 用户点击顶部筛选标签后，按服务端支持的状态重新查询。 */
    public void selectStatus(String status) {
        if (equalsNullable(selectedStatus, status)) return;
        selectedStatus = status;
        refresh();
    }

    /** 滚动到底部时加载下一页；防止并发触发重复请求。 */
    public void loadMore() {
        if (loading || loadingMore || !hasMore || !firstLoaded) return;
        // 第一页失败时不能从第 1 页的“下一页”开始，应重新请求第一页。
        if (currentPage <= 0) {
            refresh();
            return;
        }
        loadPage(requestVersion, currentPage + 1, false);
    }

    /** 请求某一页会话记录。 */
    private void loadPage(final int version, final int page, final boolean firstPage) {
        if (firstPage) {
            loading = true;
            loadingMore = false;
        } else {
            loadingMore = true;
        }
        errorMessage = null;
        publish();

        repository.getSessions(selectedStatus, page, PAGE_SIZE,
                new ApiCallback<PageResponse<SessionListItem>>() {
            @Override
            public void onSuccess(PageResponse<SessionListItem> result) {
                if (version != requestVersion) return;

                List<SessionListItem> pageItems = result == null ? null : result.getItems();
                if (firstPage) sessions.clear();
                if (pageItems != null) sessions.addAll(pageItems);

                currentPage = page;
                totalRecords = result == null ? sessions.size() : result.getTotal();
                hasMore = pageItems != null && !pageItems.isEmpty()
                        && currentPage * PAGE_SIZE < totalRecords;
                loading = false;
                loadingMore = false;
                publish();
            }

            @Override
            public void onError(ApiException error) {
                if (version != requestVersion) return;
                loading = false;
                loadingMore = false;
                errorMessage = error == null ? "加载练习记录失败" : error.getMessage();
                publish();
            }
        });
    }

    /** 把用户统计响应中的练习次数、题量、样本充分时的正确率写入页面状态。 */
    private void applyStatistics(UserStatisticsResponse result) {
        if (result == null) return;

        UserPracticeSummary practice = result.getPracticeSummary();
        if (practice != null) {
            totalPracticeCount = practice.getSessionTotal();
        }

        UserAnswerSummary answers = result.getAnswerSummary();
        if (answers != null) {
            totalAnsweredQuestions = answers.getAnsweredQuestionCount();
            // 后端在 insufficient_samples 时会把 accuracy 置为 null，客户端不猜测数值。
            averageAccuracy = "available".equalsIgnoreCase(answers.getDisplayStatus())
                    ? answers.getAccuracy() : null;
        }
    }

    /** 将当前 ViewModel 字段复制为不可变 UI 状态，通知页面刷新。 */
    private void publish() {
        uiState.setValue(new RecordsUiState(
                loading,
                loadingMore,
                selectedStatus,
                sessions,
                paperTitles,
                totalRecords,
                hasMore,
                totalPracticeCount,
                totalAnsweredQuestions,
                averageAccuracy,
                errorMessage
        ));
    }

    /** 比较允许为 null 的筛选状态。 */
    private boolean equalsNullable(String first, String second) {
        return first == null ? second == null : first.equals(second);
    }
}
