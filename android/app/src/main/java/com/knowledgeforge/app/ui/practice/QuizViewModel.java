package com.knowledgeforge.app.ui.practice;

import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;

import androidx.lifecycle.LiveData;
import androidx.lifecycle.MutableLiveData;
import androidx.lifecycle.ViewModel;

import com.knowledgeforge.app.data.repository.PracticeRepository;
import com.knowledgeforge.app.network.callback.ApiCallback;
import com.knowledgeforge.app.network.model.ApiException;
import com.knowledgeforge.app.network.model.DraftSaveRequest;
import com.knowledgeforge.app.network.model.DraftSaveResponse;
import com.knowledgeforge.app.network.model.MarkItemResponse;
import com.knowledgeforge.app.network.model.MarkRequest;
import com.knowledgeforge.app.network.model.SessionDetailItem;
import com.knowledgeforge.app.network.model.SessionDetailResponse;
import com.knowledgeforge.app.network.model.SessionResponse;
import com.knowledgeforge.app.network.model.SubmitAnswerRequest;
import com.knowledgeforge.app.network.model.SubmitAnswerResponse;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * 刷题页面的业务状态管理器。
 *
 * <p>主要工作：</p>
 * <ol>
 *     <li>通过 Repository 加载服务端会话详情；</li>
 *     <li>按题型保存答案，支持 String / List&lt;String&gt; / Boolean 三种 JSON 结构；</li>
 *     <li>处理提交、草稿保存、题目标记、题序进度和整卷交卷；</li>
 *     <li>维护正向累计计时，并通过 QuizTimerStorage 持久化；</li>
 *     <li>将所有页面状态封装成 QuizUiState 发布给 Fragment。</li>
 * </ol>
 *
 * <p>它不直接持有 Activity/Fragment，也不读写任何 Android View。</p>
 */
public class QuizViewModel extends ViewModel {

    /** 后端单选题的 question_type 编码。 */
    public static final String TYPE_SINGLE_CHOICE = "SINGLE_CHOICE";
    /** 后端多选题的 question_type 编码。 */
    public static final String TYPE_MULTIPLE_CHOICE = "MULTIPLE_CHOICE";
    /** 后端判断题的 question_type 编码。 */
    public static final String TYPE_TRUE_FALSE = "TRUE_FALSE";
    /** 后端简答题的 question_type 编码。 */
    public static final String TYPE_SHORT_ANSWER = "SHORT_ANSWER";

    /** Repository 负责调用项目现有练习接口。 */
    private final PracticeRepository repository;
    /** 本地计时存储，按 session_id 分别保存累计时间。 */
    private final QuizTimerStorage timerStorage;
    /** 当前页面状态；Fragment 观察该 LiveData 后刷新控件。 */
    private final MutableLiveData<QuizUiState> uiState = new MutableLiveData<>();
    /** 主线程 Handler：负责 1 秒一次的计时刷新。 */
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    /** 当前页面所处的练习会话 ID。 */
    private int sessionId = -1;
    /** 从服务端加载的会话详情；包含 paper/session/items/progress。 */
    private SessionDetailResponse detail;
    /** 当前显示的题目下标，从 0 开始。 */
    private int currentIndex;
    /** 页面是否正在首次读取会话详情。 */
    private boolean loading;
    /** 当前题是否正在提交答案。 */
    private boolean submitting;
    /** 当前题是否正在提交标记状态。 */
    private boolean marking;
    /** 是否正在请求交卷。 */
    private boolean completing;
    /** 会话是否已经完成，完成后不再启动计时或写入答案。 */
    private boolean completed;
    /** 是否已完成整卷并允许进入完整结果页；abandoned 会话不进入结果页。 */
    private boolean resultReady;
    /** 是否正在按题序把所有已填写草稿提交给后端判分。 */
    private boolean submittingAllAnswers;
    /** 页面最后一次需要展示的错误消息。 */
    private String errorMessage;

    /** 每道题当前显示/编辑的答案；key 是 paper_item_id。 */
    private final Map<Integer, Object> answers = new LinkedHashMap<>();
    /** 保存用户已经标记的题目 ID。 */
    private final Set<Integer> markedItemIds = new LinkedHashSet<>();
    /** 当前页面提交成功后取得的判分结果；首次加载的既有结果仍在 SessionDetailItem 中。 */
    private final Map<Integer, SubmitAnswerResponse> submitResults = new LinkedHashMap<>();
    /** 整卷提交中某题请求失败时保留原请求体；重试复用幂等键，防止重复生成答题记录。 */
    private final Map<Integer, SubmitAnswerRequest> pendingSubmitRequests = new LinkedHashMap<>();
    /** 已发生修改、需要发送到草稿接口的题目 ID。 */
    private final Set<Integer> dirtyDraftItemIds = new LinkedHashSet<>();
    /** 当前正在请求保存草稿的题目 ID，防止同一题出现并发覆盖。 */
    private final Set<Integer> savingDraftItemIds = new LinkedHashSet<>();

    /** 已累计的练习时间，不包含当前正在运行的这一段。 */
    private long accumulatedMillis;
    /** 当前前台计时段开始时的 SystemClock.elapsedRealtime()。 */
    private long timerSegmentStartRealtime;
    /** 当前页面显示的总累计毫秒数。 */
    private long elapsedMillis;
    /** 计时器是否正在运行。 */
    private boolean timerRunning;

    /**
     * 每秒刷新一次计时显示，同时把最新累计毫秒数写入本地存储。
     *
     * <p>每秒保存一次能降低进程被系统直接杀死时的计时丢失范围；SharedPreferences.apply()
     * 不会同步阻塞主线程。</p>
     */
    private final Runnable timerTick = new Runnable() {
        @Override
        public void run() {
            if (!timerRunning) return;
            elapsedMillis = accumulatedMillis
                    + Math.max(0L, SystemClock.elapsedRealtime() - timerSegmentStartRealtime);
            timerStorage.saveElapsedMillis(sessionId, elapsedMillis);
            publish();
            mainHandler.postDelayed(this, 1000L);
        }
    };

    /**
     * 创建 ViewModel。
     *
     * @param repository   已复用应用级网络客户端的练习数据仓库
     * @param timerStorage 按会话 ID 读写本地累计用时的工具
     */
    public QuizViewModel(PracticeRepository repository, QuizTimerStorage timerStorage) {
        this.repository = repository;
        this.timerStorage = timerStorage;
        publish();
    }

    /** @return 刷题页面状态；Fragment 应通过 LifecycleOwner 观察它 */
    public LiveData<QuizUiState> getUiState() {
        return uiState;
    }

    /**
     * 加载会话详情。
     *
     * <p>组卷接口已经自动创建 session；继续练习入口在导航前已经调用 resumeSession。
     * 因此此处只调用 GET /sessions/{id}，避免重复恢复会话。该 GET 同时返回全部题目、
     * 每题 draft_answer/is_marked/status 和恢复所需 current_item_order。</p>
     *
     * @param requestedSessionId 从导航参数传入的练习会话 ID
     */
    public void loadSession(int requestedSessionId) {
        if (requestedSessionId <= 0) {
            errorMessage = "练习会话编号无效";
            publish();
            return;
        }
        if (sessionId == requestedSessionId && (loading || detail != null)) {
            return;
        }

        sessionId = requestedSessionId;
        resultReady = false;
        submittingAllAnswers = false;
        waitingToComplete = false;
        completed = false;
        loading = true;
        errorMessage = null;
        publish();

        repository.getSessionDetail(sessionId, new ApiCallback<SessionDetailResponse>() {
            @Override
            public void onSuccess(SessionDetailResponse response) {
                loading = false;
                if (response == null || response.getSession() == null
                        || response.getItems() == null || response.getItems().isEmpty()) {
                    errorMessage = "练习会话没有返回题目，请返回练习页刷新后重试";
                    publish();
                    return;
                }

                detail = response;
                // 服务端通常已经按题序返回，这里再显式排序，避免列表顺序异常影响答题卡。
                Collections.sort(detail.getItems(), Comparator.comparingInt(SessionDetailItem::getSortOrder));

                // 恢复上次浏览位置。progress 优先，其次使用 session.current_item_order。
                int savedOrder = response.getProgress() == null
                        ? response.getSession().getCurrentItemOrder()
                        : response.getProgress().getCurrentItemOrder();
                currentIndex = Math.max(0, Math.min(detail.getItems().size() - 1, savedOrder - 1));

                answers.clear();
                markedItemIds.clear();
                submitResults.clear();
                pendingSubmitRequests.clear();
                dirtyDraftItemIds.clear();
                savingDraftItemIds.clear();

                // 从服务端逐题恢复答案、草稿和标记状态。
                for (SessionDetailItem item : detail.getItems()) {
                    if (item == null) continue;
                    int itemId = item.getPaperItemId();
                    if (item.isMarked()) markedItemIds.add(itemId);

                    Object answer = readAnswerFromItem(item);
                    if (answer != null) answers.put(itemId, copyAnswer(answer));
                }

                // 恢复客户端累计用时。completed 会话优先使用后端最终 duration_ms。
                Long serverDuration = response.getSession().getDurationMs();
                long localDuration = timerStorage.getElapsedMillis(sessionId);
                String sessionStatus = response.getSession().getStatus();
                errorMessage = null;

                if ("completed".equals(sessionStatus)) {
                    completed = true;
                    resultReady = true;
                    elapsedMillis = serverDuration == null ? localDuration : serverDuration;
                    accumulatedMillis = elapsedMillis;
                    timerStorage.clear(sessionId);
                } else if ("abandoned".equals(sessionStatus)) {
                    // 被放弃的会话仍可查看已经提交的答案，但不能继续编辑或提交。
                    // abandoned 并非正常交卷，因此不跳转到整卷成绩页。
                    completed = true;
                    resultReady = false;
                    elapsedMillis = serverDuration == null ? localDuration : serverDuration;
                    accumulatedMillis = elapsedMillis;
                    timerStorage.clear(sessionId);
                } else {
                    completed = false;
                    resultReady = false;
                    elapsedMillis = localDuration;
                    accumulatedMillis = localDuration;
                }

                publish();
            }

            @Override
            public void onError(ApiException error) {
                loading = false;
                errorMessage = safeMessage(error, "加载练习题目失败，请检查网络后重试");
                publish();
            }
        });
    }

    /**
     * 页面进入前台时开始计时。
     *
     * <p>计时器只累计刷题页处于前台的时长。页面进入后台时由 pauseTimerAndSave() 停止，
     * 再次回到前台时从之前的累计值继续，不把后台闲置时间算作答题时间。</p>
     */
    public void resumeTimer() {
        if (detail == null || completed || timerRunning || sessionId <= 0) return;
        timerRunning = true;
        timerSegmentStartRealtime = SystemClock.elapsedRealtime();
        mainHandler.removeCallbacks(timerTick);
        mainHandler.post(timerTick);
    }

    /**
     * 页面进入后台时停止计时，并保存当前题草稿和题序。
     * 该方法可从 Fragment.onStop() 调用。
     */
    public void pauseTimerAndSave() {
        pauseTimerOnly();
        if (detail == null || completed) return;
        persistCurrentDraft();
        updateServerProgress(currentIndex + 1);
        timerStorage.saveElapsedMillis(sessionId, elapsedMillis);
    }

    /** 停止正在运行的计时段，保留累计结果。 */
    private void pauseTimerOnly() {
        if (!timerRunning) return;
        elapsedMillis = accumulatedMillis
                + Math.max(0L, SystemClock.elapsedRealtime() - timerSegmentStartRealtime);
        accumulatedMillis = elapsedMillis;
        timerRunning = false;
        mainHandler.removeCallbacks(timerTick);
        if (sessionId > 0) timerStorage.saveElapsedMillis(sessionId, elapsedMillis);
        publish();
    }

    /** 获取截至当前时刻的累计时间，考虑当前计时段尚未写回 elapsedMillis 的部分。 */
    private long getCurrentElapsedMillis() {
        if (timerRunning) {
            return accumulatedMillis
                    + Math.max(0L, SystemClock.elapsedRealtime() - timerSegmentStartRealtime);
        }
        return elapsedMillis;
    }

    /**
     * 修改当前题答案。
     *
     * @param answer 单选/简答为 String，多选为 List&lt;String&gt;，判断为 Boolean
     */
    public void setCurrentAnswer(Object answer) {
        SessionDetailItem item = getCurrentItem();
        if (item == null || completed || submitting || completing || waitingToComplete
                || submittingAllAnswers || isItemSubmitted(item)) return;

        Object copied = copyAnswer(answer);
        int itemId = item.getPaperItemId();
        Object oldAnswer = answers.get(itemId);
        // 同一题答案发生改变时，旧提交幂等键对应的请求内容已不再相同，必须废弃。
        // 如果答案未改变，则保留失败请求的幂等键，下一次重试会复用原请求体。
        if (!answersEqual(oldAnswer, copied)) pendingSubmitRequests.remove(itemId);
        answers.put(itemId, copied);
        dirtyDraftItemIds.add(itemId);
        errorMessage = null;
        publish();
    }

    /**
     * 切换到指定题目。
     * 在切题之前保存旧题草稿，并把新题序同步给后端。
     *
     * @param targetIndex 目标题目下标，从 0 开始
     */
    public void moveToQuestion(int targetIndex) {
        if (detail == null || completed || completing || waitingToComplete || submittingAllAnswers
                || targetIndex < 0 || targetIndex >= detail.getItems().size()
                || targetIndex == currentIndex) return;

        persistDraftAt(currentIndex);
        currentIndex = targetIndex;
        errorMessage = null;
        publish();
        updateServerProgress(currentIndex + 1);
    }

    /**
     * 标记/取消标记当前题。
     *
     * <p>标记是会话题目项级别的状态，与是否答题相互独立；服务端成功后才更新本地状态。</p>
     */
    public void toggleCurrentMark() {
        SessionDetailItem item = getCurrentItem();
        if (item == null || completed || completing || waitingToComplete
                || submittingAllAnswers || marking) return;

        final int itemId = item.getPaperItemId();
        final boolean nextMarked = !markedItemIds.contains(itemId);
        marking = true;
        publish();

        repository.markItem(sessionId, itemId, new MarkRequest(nextMarked),
                new ApiCallback<MarkItemResponse>() {
                    @Override
                    public void onSuccess(MarkItemResponse response) {
                        marking = false;
                        boolean marked = response == null ? nextMarked : response.isMarked();
                        if (marked) markedItemIds.add(itemId);
                        else markedItemIds.remove(itemId);
                        errorMessage = null;
                        publish();
                    }

                    @Override
                    public void onError(ApiException error) {
                        marking = false;
                        errorMessage = safeMessage(error, "标记状态保存失败");
                        publish();
                    }
                });
    }

    /**
     * 用户确认整卷交卷。
     * 先保存全部待同步草稿，再按题序统一提交已填写答案判分，最后调用完成会话接口。
     */
    public void completeSession() {
        if (detail == null || completed || completing || waitingToComplete || submittingAllAnswers) return;
        if (marking) {
            errorMessage = "题目标记正在保存，请稍后再交卷";
            publish();
            return;
        }

        // 切题时保存的草稿请求可能还在飞行中。交卷前等待所有已修改草稿保存完毕，
        // 防止 complete 先成功导致后续 draft 被后端按 completed 状态拒绝。
        if (!dirtyDraftItemIds.isEmpty() || !savingDraftItemIds.isEmpty()) {
            waitingToComplete = true;
            publish();
            flushDirtyDraftsBeforeComplete();
        } else {
            submitAllAnsweredItems();
        }
    }

    /** 把所有尚未落库的题目草稿补存；全部成功后才统一提交已填写答案。 */
    private void flushDirtyDraftsBeforeComplete() {
        if (!waitingToComplete || detail == null) return;

        // 先启动所有尚未开始保存的题目。已经有请求在途的题目不重复发请求，
        // 等该请求回调后再由回调重新检查 dirtyDraftItemIds。
        List<Integer> dirtyIds = new ArrayList<>(dirtyDraftItemIds);
        for (Integer itemId : dirtyIds) {
            int index = findItemIndex(itemId == null ? -1 : itemId);
            if (index >= 0 && !savingDraftItemIds.contains(itemId)) {
                persistDraftAt(index);
            }
        }

        // 如果所有题的草稿都已成功保存且不存在进行中的请求，才发送 complete。
        if (dirtyDraftItemIds.isEmpty() && savingDraftItemIds.isEmpty()) {
            waitingToComplete = false;
            submitAllAnsweredItems();
        }
    }

    /**
     * 统一交卷时，按试卷顺序提交所有已填写但尚未判分的答案。
     *
     * <p>答题过程中只保存草稿，不对单题调用 submit；用户点击最终“交卷”后才在这里逐题
     * 调用后端判分接口。已提交的题目会跳过，网络失败的题目保留原请求和幂等键，
     * 下次点击交卷时只重试失败部分，不会重复生成已经成功的答题记录。</p>
     */
    private void submitAllAnsweredItems() {
        if (detail == null || completed || submittingAllAnswers || completing) return;

        List<Integer> pendingItemIds = new ArrayList<>();
        for (SessionDetailItem item : detail.getItems()) {
            if (item == null || isItemSubmitted(item)) continue;
            Object answer = answers.get(item.getPaperItemId());
            if (!isEmptyAnswer(answer)) {
                pendingItemIds.add(item.getPaperItemId());
            }
        }

        // 没有待判分答案时也允许交卷，空白题会在结果页显示“未作答”。
        if (pendingItemIds.isEmpty()) {
            completeSessionInternal();
            return;
        }

        submittingAllAnswers = true;
        errorMessage = null;
        publish();
        submitPendingAnswerAt(pendingItemIds, 0);
    }

    /**
     * 顺序提交交卷队列中的下一题。
     * 使用串行请求，避免大量题目同时请求造成服务器压力，也方便明确定位失败题序。
     */
    private void submitPendingAnswerAt(final List<Integer> itemIds, final int queueIndex) {
        if (queueIndex >= itemIds.size()) {
            submittingAllAnswers = false;
            publish();
            completeSessionInternal();
            return;
        }

        final int itemId = itemIds.get(queueIndex);
        final int itemIndex = findItemIndex(itemId);
        if (itemIndex < 0 || itemIndex >= detail.getItems().size()) {
            submitPendingAnswerAt(itemIds, queueIndex + 1);
            return;
        }

        final Object answer = copyAnswer(answers.get(itemId));
        if (isEmptyAnswer(answer)) {
            submitPendingAnswerAt(itemIds, queueIndex + 1);
            return;
        }

        SubmitAnswerRequest request = pendingSubmitRequests.get(itemId);
        if (request == null || !answersEqual(request.getAnswer(), answer)) {
            // 此请求只会在交卷阶段创建；失败重试时保留同一请求体和幂等键。
            String idempotencyKey = UUID.randomUUID().toString().replace("-", "");
            request = new SubmitAnswerRequest(copyAnswer(answer), idempotencyKey);
            pendingSubmitRequests.put(itemId, request);
        }

        final SubmitAnswerRequest stableRequest = request;
        repository.submitAnswer(sessionId, itemId, stableRequest,
                new ApiCallback<SubmitAnswerResponse>() {
                    @Override
                    public void onSuccess(SubmitAnswerResponse response) {
                        if (response == null) {
                            submittingAllAnswers = false;
                            errorMessage = "第 " + (itemIndex + 1)
                                    + " 题提交后未收到判分结果，请重新交卷重试";
                            publish();
                            return;
                        }
                        submitResults.put(itemId, response);
                        pendingSubmitRequests.remove(itemId);
                        dirtyDraftItemIds.remove(itemId);
                        publish();
                        submitPendingAnswerAt(itemIds, queueIndex + 1);
                    }

                    @Override
                    public void onError(ApiException error) {
                        // 不移除 pendingSubmitRequests：下次点击交卷会使用同一个幂等键重试。
                        submittingAllAnswers = false;
                        errorMessage = "第 " + (itemIndex + 1) + " 题提交失败："
                                + safeMessage(error, "网络异常，请重试");
                        publish();
                    }
                });
    }

    /** 在当前会话题目列表中查找 paper_item_id 对应的下标。 */
    private int findItemIndex(int paperItemId) {
        if (detail == null || detail.getItems() == null) return -1;
        for (int i = 0; i < detail.getItems().size(); i++) {
            SessionDetailItem item = detail.getItems().get(i);
            if (item != null && item.getPaperItemId() == paperItemId) return i;
        }
        return -1;
    }

    /** 所有已填写答案判分成功后调用后端完成接口，完成后由 Fragment 导航到整卷结果页。 */
    private void completeSessionInternal() {
        if (completing || completed || sessionId <= 0) return;
        completing = true;
        errorMessage = null;
        pauseTimerOnly();
        timerStorage.saveElapsedMillis(sessionId, elapsedMillis);
        publish();

        repository.completeSession(sessionId, new ApiCallback<SessionResponse>() {
            @Override
            public void onSuccess(SessionResponse response) {
                completing = false;
                submittingAllAnswers = false;
                completed = true;
                resultReady = true;
                if (response != null && response.getDurationMs() != null) {
                    elapsedMillis = response.getDurationMs();
                }
                accumulatedMillis = elapsedMillis;
                timerStorage.clear(sessionId);
                errorMessage = null;
                publish();
                // Fragment 收到 resultReady 后跳转到独立的整卷结果页；结果页再读取一次
                // GET /sessions/{id}/result，避免把所有题目塞进单题答题页或弹窗。
            }

            @Override
            public void onError(ApiException error) {
                completing = false;
                submittingAllAnswers = false;
                errorMessage = safeMessage(error, "交卷失败，请检查网络后重试");
                // 不在网络回调中无条件重启计时，避免页面已经进入后台后仍累计时间。
                // 页面仍在前台时，Fragment 收到这次状态更新会通过 render() 重新启动计时。
                publish();
            }
        });
    }

    /** 将当前题的进度位置同步到后端；网络失败不影响本地翻题。 */
    private void updateServerProgress(int currentOrder) {
        if (sessionId <= 0 || detail == null || completed) return;
        repository.updateProgress(sessionId, currentOrder, new ApiCallback<com.knowledgeforge.app.network.model.ProgressUpdateResponse>() {
            @Override public void onSuccess(com.knowledgeforge.app.network.model.ProgressUpdateResponse response) {
                // 当前题序以本地页面为准；服务端成功后无需额外操作。
            }
            @Override public void onError(ApiException error) {
                // 进度保存失败不阻断答题；下次切题或 onStop 时会再次同步。
            }
        });
    }

    /** 页面切题或进入后台时保存当前题草稿。 */
    private void persistCurrentDraft() {
        persistDraftAt(currentIndex);
    }

    /**
     * 保存指定题的草稿。
     *
     * @param itemIndex 题目下标
     */
    private void persistDraftAt(int itemIndex) {
        if (detail == null || completed || itemIndex < 0 || itemIndex >= detail.getItems().size()) {
            return;
        }
        SessionDetailItem item = detail.getItems().get(itemIndex);
        int itemId = item.getPaperItemId();
        if (!dirtyDraftItemIds.contains(itemId)) {
            return;
        }

        // 相同题目上一份保存还未返回时，不并发发送同一题的草稿请求。
        // 如果答案在请求期间发生变化，dirtyDraftItemIds 会继续保留该题 ID，
        // 当前请求成功后会读取最新答案再补发一次。
        if (savingDraftItemIds.contains(itemId)) {
            return;
        }

        Object snapshotAnswer = copyAnswer(answers.get(itemId));
        savingDraftItemIds.add(itemId);
        repository.saveDraft(sessionId, itemId, new DraftSaveRequest(snapshotAnswer),
                new ApiCallback<DraftSaveResponse>() {
                    @Override
                    public void onSuccess(DraftSaveResponse response) {
                        savingDraftItemIds.remove(itemId);
                        boolean changedDuringRequest = !answersEqual(
                                answers.get(itemId), snapshotAnswer);
                        if (!changedDuringRequest) dirtyDraftItemIds.remove(itemId);

                        // 如果请求期间答案被修改，旧快照不能覆盖最新答案，继续补存最新值。
                        if (dirtyDraftItemIds.contains(itemId)) {
                            persistDraftAt(itemIndex);
                            return;
                        }

                        // 如果正在交卷等待草稿，检查这次保存后是否已经全部完成。
                        if (waitingToComplete) flushDirtyDraftsBeforeComplete();
                        publish();
                    }

                    @Override
                    public void onError(ApiException error) {
                        savingDraftItemIds.remove(itemId);
                        // 草稿仍留在 dirtyDraftItemIds 中，用户下次切题/退出时还可以重新保存。
                        // 如果这次失败发生在交卷前，则解除等待状态，不发送 complete 请求。
                        if (waitingToComplete) waitingToComplete = false;
                        errorMessage = safeMessage(error, "草稿保存失败，请重试");
                        publish();
                    }
                });
    }

    /** 正在等待草稿全部落库后再交卷；用于避免 complete 与 draft 请求竞争。 */
    private boolean waitingToComplete;

    /** 当前题对象；未加载或下标越界时返回 null。 */
    private SessionDetailItem getCurrentItem() {
        if (detail == null || detail.getItems() == null
                || currentIndex < 0 || currentIndex >= detail.getItems().size()) return null;
        return detail.getItems().get(currentIndex);
    }

    /** 判断一个题目项是否已经提交过答案。 */
    private boolean isItemSubmitted(SessionDetailItem item) {
        return item != null && ("answered".equals(item.getStatus())
                || submitResults.containsKey(item.getPaperItemId()));
    }

    /**
     * 从会话题目项中读取应该回显的答案。
     * 已提交题回显 your_answer；未提交题回显 draft_answer。
     */
    private Object readAnswerFromItem(SessionDetailItem item) {
        if (item == null) return null;
        Object raw = "answered".equals(item.getStatus())
                ? item.getYourAnswer() : item.getDraftAnswer();
        if (raw == null) return null;

        String type = item.getQuestionType();
        if (TYPE_TRUE_FALSE.equals(type)) {
            if (raw instanceof Boolean) return raw;
            if (raw instanceof String) {
                String value = ((String) raw).trim();
                if ("true".equalsIgnoreCase(value) || "1".equals(value)) return Boolean.TRUE;
                if ("false".equalsIgnoreCase(value) || "0".equals(value)) return Boolean.FALSE;
            }
            return raw;
        }
        if (TYPE_MULTIPLE_CHOICE.equals(type)) {
            if (raw instanceof List) return copyAnswer(raw);
            // 兼容旧缓存/旧接口偶尔返回 "A,C" 字符串的情况；当前接口契约仍以数组为准。
            if (raw instanceof String) {
                List<String> values = new ArrayList<>();
                for (String value : ((String) raw).split(",")) {
                    if (!value.trim().isEmpty()) values.add(value.trim());
                }
                return values;
            }
        }
        return raw;
    }

    /** 拷贝多选题 List，防止 View 层修改集合时污染 ViewModel 状态。 */
    private Object copyAnswer(Object answer) {
        if (answer instanceof List) return new ArrayList<>((List<?>) answer);
        return answer;
    }

    /** 比较两种答案是否一致，特别处理多选题数组。 */
    private boolean answersEqual(Object first, Object second) {
        if (first == second) return true;
        if (first == null || second == null) return false;
        if (first instanceof List && second instanceof List) {
            return ((List<?>) first).equals((List<?>) second);
        }
        return first.equals(second);
    }

    /** 判断答案是否为空；Boolean.FALSE 是有效的判断题答案，不能当作空值。 */
    private boolean isEmptyAnswer(Object answer) {
        if (answer == null) return true;
        if (answer instanceof String) return ((String) answer).trim().isEmpty();
        if (answer instanceof List) return ((List<?>) answer).isEmpty();
        return false;
    }

    /** 将错误对象转换为稳定的用户提示。 */
    private String safeMessage(ApiException error, String fallback) {
        if (error == null || error.getMessage() == null || error.getMessage().trim().isEmpty()) {
            return fallback;
        }
        return error.getMessage();
    }

    /** 创建并发布当前完整 UI 状态快照。 */
    private void publish() {
        uiState.setValue(new QuizUiState(
                loading, submitting, marking,
                completing || waitingToComplete || submittingAllAnswers, completed, resultReady,
                detail, currentIndex, getCurrentElapsedMillis(), answers,
                markedItemIds, submitResults, errorMessage));
    }

    /** ViewModel 被彻底销毁时停止 Handler，防止计时任务继续持有页面业务对象。 */
    @Override
    protected void onCleared() {
        pauseTimerOnly();
        mainHandler.removeCallbacks(timerTick);
        super.onCleared();
    }
}
