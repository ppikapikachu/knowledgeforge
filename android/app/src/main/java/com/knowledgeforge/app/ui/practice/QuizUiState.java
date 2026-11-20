package com.knowledgeforge.app.ui.practice;

import com.knowledgeforge.app.network.model.SessionDetailResponse;
import com.knowledgeforge.app.network.model.SessionDetailItem;
import com.knowledgeforge.app.network.model.SubmitAnswerResponse;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 刷题页面的一次 UI 状态快照。
 *
 * <p>ViewModel 每当题目、答案、标记、计时或网络状态发生变化时，都会创建新的
 * QuizUiState 并通过 LiveData 发布。QuizFragment 只读取这里的数据来更新控件。</p>
 *
 * <p>本类不发起网络请求，不计算答案，也不操作 Android View。</p>
 */
public class QuizUiState {

    /** 是否正在首次加载会话详情。 */
    private final boolean loading;
    /** 是否正在提交当前题答案。 */
    private final boolean submitting;
    /** 是否正在保存标记状态。 */
    private final boolean marking;
    /** 是否正在完成整份练习。 */
    private final boolean completing;
    /** 当前会话是否已完成；完成后进入只读回顾状态。 */
    private final boolean completed;
    /** 是否属于正常交卷完成态；为 true 时应跳转到整卷结果页。 */
    private final boolean resultReady;
    /** 当前会话详情，包含试卷标题、题目快照、草稿、标记和进度。 */
    private final SessionDetailResponse detail;
    /** 当前题目下标，从 0 开始。 */
    private final int currentIndex;
    /** 当前练习累计时长，单位毫秒。 */
    private final long elapsedMillis;
    /** 每道题当前编辑中的答案，key 为 paper_item_id。 */
    private final Map<Integer, Object> answers;
    /** 每道题当前是否被标记，key 为 paper_item_id。 */
    private final Set<Integer> markedItemIds;
    /** 本次进入页面后新提交成功的判分结果，key 为 paper_item_id。 */
    private final Map<Integer, SubmitAnswerResponse> submitResults;
    /** 当前需要展示给用户的错误文本；为空表示没有错误。 */
    private final String errorMessage;

    /**
     * 创建页面状态快照。集合在此处复制，避免外部随后修改源集合影响已发布状态。
     */
    public QuizUiState(boolean loading,
                       boolean submitting,
                       boolean marking,
                       boolean completing,
                       boolean completed,
                       boolean resultReady,
                       SessionDetailResponse detail,
                       int currentIndex,
                       long elapsedMillis,
                       Map<Integer, Object> answers,
                       Set<Integer> markedItemIds,
                       Map<Integer, SubmitAnswerResponse> submitResults,
                       String errorMessage) {
        this.loading = loading;
        this.submitting = submitting;
        this.marking = marking;
        this.completing = completing;
        this.completed = completed;
        this.resultReady = resultReady;
        this.detail = detail;
        this.currentIndex = currentIndex;
        this.elapsedMillis = elapsedMillis;
        this.answers = answers == null ? new LinkedHashMap<>() : new LinkedHashMap<>(answers);
        this.markedItemIds = markedItemIds == null
                ? new LinkedHashSet<>() : new LinkedHashSet<>(markedItemIds);
        this.submitResults = submitResults == null
                ? new LinkedHashMap<>() : new LinkedHashMap<>(submitResults);
        this.errorMessage = errorMessage;
    }

    /** @return 是否正在加载会话详情 */
    public boolean isLoading() { return loading; }
    /** @return 是否正在提交当前题 */
    public boolean isSubmitting() { return submitting; }
    /** @return 是否正在保存当前题标记 */
    public boolean isMarking() { return marking; }
    /** @return 是否正在交卷 */
    public boolean isCompleting() { return completing; }
    /** @return 会话是否已完成（包含 abandoned 只读状态） */
    public boolean isCompleted() { return completed; }
    /** @return 是否正常交卷完成，可进入整卷结果页 */
    public boolean isResultReady() { return resultReady; }
    /** @return 当前会话详情 */
    public SessionDetailResponse getDetail() { return detail; }
    /** @return 当前题目下标（从 0 开始） */
    public int getCurrentIndex() { return currentIndex; }
    /** @return 当前累计练习毫秒数 */
    public long getElapsedMillis() { return elapsedMillis; }
    /** @return 每题当前答案映射 */
    public Map<Integer, Object> getAnswers() { return answers; }
    /** @return 已标记题目的 paper_item_id 集合 */
    public Set<Integer> getMarkedItemIds() { return markedItemIds; }
    /** @return 当前页面运行期间刚提交的判分结果 */
    public Map<Integer, SubmitAnswerResponse> getSubmitResults() { return submitResults; }
    /** @return 当前错误信息 */
    public String getErrorMessage() { return errorMessage; }

    /** @return 当前会话中的题目列表；会话未加载时返回空列表 */
    public List<SessionDetailItem> getItems() {
        if (detail == null || detail.getItems() == null) return new ArrayList<>();
        return detail.getItems();
    }

    /** @return 当前题目；没有有效题目时返回 null */
    public SessionDetailItem getCurrentItem() {
        List<SessionDetailItem> items = getItems();
        return currentIndex < 0 || currentIndex >= items.size() ? null : items.get(currentIndex);
    }

    /** @return 试卷标题；未加载时返回默认标题 */
    public String getPaperTitle() {
        return detail == null || detail.getPaper() == null
                || detail.getPaper().getTitle() == null
                ? "刷题练习" : detail.getPaper().getTitle();
    }

    /** @return 题目总数 */
    public int getTotalCount() { return getItems().size(); }

    /** @return 当前题的答案；按题型可能是 String、List&lt;String&gt; 或 Boolean */
    public Object getAnswer(int paperItemId) { return answers.get(paperItemId); }

    /** @return 指定题目是否已在后端提交过或本次页面提交成功 */
    public boolean isItemAnswered(SessionDetailItem item) {
        return item != null && ("answered".equals(item.getStatus())
                || submitResults.containsKey(item.getPaperItemId()));
    }

    /** @return 指定题目是否已标记 */
    public boolean isItemMarked(SessionDetailItem item) {
        return item != null && markedItemIds.contains(item.getPaperItemId());
    }

    /**
     * 判断用户是否已经填写答案（包括只保存为草稿、尚未统一交卷的题目）。
     * 与 isItemAnswered 不同：本方法用于答题卡和作答进度，不代表后端已经判分。
     */
    public boolean hasUserAnswer(SessionDetailItem item) {
        if (item == null) return false;
        if (isItemAnswered(item)) return true;
        Object answer = answers.get(item.getPaperItemId());
        if (answer == null) return false;
        if (answer instanceof String) return !((String) answer).trim().isEmpty();
        if (answer instanceof List) return !((List<?>) answer).isEmpty();
        // Boolean.FALSE 是判断题有效答案，不能当成未作答。
        return true;
    }

    /** @return 已经填写答案的题目数量（草稿也算已答） */
    public int getAnsweredCount() {
        int count = 0;
        for (SessionDetailItem item : getItems()) {
            if (hasUserAnswer(item)) count++;
        }
        return count;
    }

    /** @return 尚未填写答案的题目数量 */
    public int getUnansweredCount() {
        return Math.max(0, getTotalCount() - getAnsweredCount());
    }
}
