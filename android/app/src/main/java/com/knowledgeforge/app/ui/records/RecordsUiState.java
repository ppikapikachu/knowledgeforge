package com.knowledgeforge.app.ui.records;

import com.knowledgeforge.app.network.model.SessionListItem;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 练习记录页面的只读 UI 状态。
 * Fragment 只观察这个对象并刷新 View，不直接拼接网络响应。
 */
public class RecordsUiState {

    /** 首次加载或切换筛选时是否正在请求列表。 */
    private final boolean loading;
    /** 上拉到底部后是否正在请求下一页。 */
    private final boolean loadingMore;
    /** 当前筛选状态：null=全部，其他为后端支持的会话状态。 */
    private final String selectedStatus;
    /** 当前已经加载的会话记录。 */
    private final List<SessionListItem> sessions;
    /** 试卷 ID 到试卷标题的映射，供会话记录显示标题。 */
    private final Map<Integer, String> paperTitles;
    /** 服务端符合当前筛选条件的总会话数。 */
    private final int totalRecords;
    /** 是否还有下一页。 */
    private final boolean hasMore;
    /** 统计接口返回的总练习次数。 */
    private final int totalPracticeCount;
    /** 统计接口返回的至少作答过一次的题目数量。 */
    private final int totalAnsweredQuestions;
    /** 总体正确率；样本不足时为 null。 */
    private final Double averageAccuracy;
    /** 列表请求错误文本；空值表示无错误。 */
    private final String errorMessage;

    public RecordsUiState(boolean loading,
                          boolean loadingMore,
                          String selectedStatus,
                          List<SessionListItem> sessions,
                          Map<Integer, String> paperTitles,
                          int totalRecords,
                          boolean hasMore,
                          int totalPracticeCount,
                          int totalAnsweredQuestions,
                          Double averageAccuracy,
                          String errorMessage) {
        this.loading = loading;
        this.loadingMore = loadingMore;
        this.selectedStatus = selectedStatus;
        this.sessions = sessions == null
                ? Collections.emptyList()
                : Collections.unmodifiableList(new ArrayList<>(sessions));
        this.paperTitles = paperTitles == null
                ? Collections.emptyMap()
                : Collections.unmodifiableMap(new HashMap<>(paperTitles));
        this.totalRecords = totalRecords;
        this.hasMore = hasMore;
        this.totalPracticeCount = totalPracticeCount;
        this.totalAnsweredQuestions = totalAnsweredQuestions;
        this.averageAccuracy = averageAccuracy;
        this.errorMessage = errorMessage;
    }

    /** 创建页面刚打开时的初始状态。 */
    public static RecordsUiState initial() {
        return new RecordsUiState(true, false, null,
                Collections.emptyList(), Collections.emptyMap(), 0, false,
                0, 0, null, null);
    }

    public boolean isLoading() { return loading; }
    public boolean isLoadingMore() { return loadingMore; }
    public String getSelectedStatus() { return selectedStatus; }
    public List<SessionListItem> getSessions() { return sessions; }
    public Map<Integer, String> getPaperTitles() { return paperTitles; }
    public int getTotalRecords() { return totalRecords; }
    public boolean hasMore() { return hasMore; }
    public int getTotalPracticeCount() { return totalPracticeCount; }
    public int getTotalAnsweredQuestions() { return totalAnsweredQuestions; }
    public Double getAverageAccuracy() { return averageAccuracy; }
    public String getErrorMessage() { return errorMessage; }

    /** 按纸卷 ID 获取标题；历史纸卷标题缺失时返回 null，由页面提供兜底文案。 */
    public String getPaperTitle(int paperId) {
        return paperTitles.get(paperId);
    }
}
