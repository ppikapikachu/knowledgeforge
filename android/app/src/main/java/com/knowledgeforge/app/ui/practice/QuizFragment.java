package com.knowledgeforge.app.ui.practice;

import android.content.DialogInterface;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.GridLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.OnBackPressedCallback;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;
import androidx.lifecycle.ViewModelProvider;
import androidx.navigation.NavController;
import androidx.navigation.NavOptions;
import androidx.navigation.fragment.NavHostFragment;

import com.google.android.material.dialog.MaterialAlertDialogBuilder;
import com.knowledgeforge.app.R;
import com.knowledgeforge.app.data.repository.PracticeRepository;
import com.knowledgeforge.app.network.ApiClient;
import com.knowledgeforge.app.network.model.QuestionOptionInfo;
import com.knowledgeforge.app.network.model.SessionDetailItem;
import com.knowledgeforge.app.network.model.SubmitAnswerResponse;

import java.util.ArrayList;
import java.util.List;

/**
 * 刷题答题页 Fragment。
 *
 * <p>本类只处理 Android 页面展示与用户交互，不直接访问 Retrofit。具体职责如下：</p>
 * <ol>
 *     <li>加载 fragment_quiz.xml 并绑定页面控件；</li>
 *     <li>观察 QuizViewModel 的状态，更新计时、题目进度、题目内容和按钮状态；</li>
 *     <li>根据 question_type 动态创建单选、多选、判断或简答控件；</li>
 *     <li>显示答题卡、退出确认，并在交卷后跳转整卷结果页；</li>
 *     <li>页面进入后台时通知 ViewModel 暂停计时并保存进度/草稿。</li>
 * </ol>
 *
 * <p>题目字段、答案 JSON 形状和网络接口全部沿用当前项目已有 Model/API。</p>
 */
public class QuizFragment extends Fragment {

    /** Navigation 参数名：本次练习的 session_id。 */
    public static final String ARG_SESSION_ID = "session_id";

    /** 页面背景和动态控件使用的主题色。 */
    private static final int COLOR_PRIMARY = Color.rgb(36, 107, 238);
    /** 页面主要文字颜色。 */
    private static final int COLOR_TEXT = Color.rgb(23, 33, 61);
    /** 页面次要文字颜色。 */
    private static final int COLOR_SECONDARY = Color.rgb(104, 115, 143);
    /** 选中题目选项的淡蓝底色。 */
    private static final int COLOR_SELECTED_BG = Color.rgb(234, 241, 255);
    /** 普通题目选项的边框颜色。 */
    private static final int COLOR_BORDER = Color.rgb(220, 228, 244);
    /** 已判对颜色。 */
    private static final int COLOR_SUCCESS = Color.rgb(22, 166, 117);
    /** 已判错颜色。 */
    private static final int COLOR_ERROR = Color.rgb(226, 86, 93);
    /** 当前题在答题卡中的强调色。 */
    private static final int COLOR_CURRENT = Color.rgb(231, 163, 45);

    // -------------------- XML 中固定存在的页面控件 --------------------

    /** 顶部试卷标题。 */
    private TextView tvTitle;
    /** 练习累计计时显示。 */
    private TextView tvTimer;
    /** 当前题序，例如 3 / 20 题。 */
    private TextView tvQuestionIndex;
    /** 已标记题量。 */
    private TextView tvMarkedCount;
    /** 已填写答案的题量（包括尚未交卷的草稿）。 */
    private TextView tvAnsweredCount;
    /** 尚未填写答案的题量。 */
    private TextView tvUnansweredCount;
    /** 当前题序的进度条。 */
    private ProgressBar progressBar;
    /** 当前题序百分比。 */
    private TextView tvProgressPercent;
    /** 首次获取会话详情时显示的加载圈。 */
    private ProgressBar loadingView;
    /** 网络或业务错误提示。点击可重新加载。 */
    private TextView tvError;
    /** 题型标签。 */
    private TextView tvQuestionType;
    /** 本题分值。 */
    private TextView tvScore;
    /** 题干文本。 */
    private TextView tvQuestionContent;
    /** 动态答案控件容器。 */
    private LinearLayout answerContainer;
    /** 答案解析卡片。仅提交后显示。 */
    private View explanationCard;
    /** 正确/错误/待人工批改状态文字。 */
    private TextView tvResultState;
    /** 正确答案文字。 */
    private TextView tvCorrectAnswer;
    /** 答案解析文字。 */
    private TextView tvExplanation;
    /** 标记/取消标记按钮。 */
    private TextView btnMark;
    /** 打开答题卡按钮。 */
    private TextView btnAnswerSheet;
    /** 下一题/最终交卷主按钮；答题过程中不提供单题提交按钮。 */
    private TextView btnPrimary;

    /** 页面 ViewModel，负责所有业务状态。 */
    private QuizViewModel viewModel;
    /** Navigation 传入的练习会话 ID。 */
    private int sessionId;
    /** 当前显示的题目 ID，用于避免每秒刷新计时都重建输入控件。 */
    private int renderedItemId = -1;
    /** 当前题是否已经提交；提交状态变化时需要重新渲染答案控件和解析。 */
    private boolean renderedSubmitted;
    /** 会话是否进入只读完成态；状态变化时需要禁用答案编辑控件。 */
    private boolean renderedCompleted;
    /** 当前题是否正在提交；状态变化时需要更新控件可编辑状态。 */
    private boolean renderedSubmitting;
    /** 是否正在统一提交整卷；此时锁定选项，避免提交中答案变化。 */
    private boolean renderedCompleting;
    /** 新提交结果的签名；避免同一题的普通计时刷新反复重建 UI。 */
    private String renderedFeedbackSignature = "";
    /** 是否已经从当前答题页跳转到整卷结果页，避免状态多次更新导致重复导航。 */
    private boolean hasNavigatedToResult;
    /** 当前答题卡弹窗；仅由 Fragment 持有，关闭时立即释放。 */
    private androidx.appcompat.app.AlertDialog answerSheetDialog;
    /** 系统返回处理器：退出前先提示并保存。 */
    private OnBackPressedCallback backPressedCallback;
    /** 当前刷题页是否处于 STARTED/前台状态；防止计时在 onStop 后被 UI 刷新意外重启。 */
    private boolean pageStarted;

    public QuizFragment() {
        // Fragment 必须保留 public 无参构造，供 Android Navigation/FragmentManager 重建。
    }

    /** 创建刷题页 XML。 */
    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater,
                             @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_quiz, container, false);
    }

    /** 页面创建完成后绑定控件、创建 ViewModel、监听状态与点击事件，并加载会话详情。 */
    @Override
    public void onViewCreated(@NonNull View root, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(root, savedInstanceState);
        bindViews(root);
        initViewModel();
        initBackHandler();
        observeViewModel();
        initListeners(root);

        sessionId = getArguments() == null ? -1 : getArguments().getInt(ARG_SESSION_ID, -1);
        viewModel.loadSession(sessionId);
    }

    /** 页面回到前台后恢复计时；如果数据还在加载，ViewModel 会在加载完成后再启动。 */
    @Override
    public void onStart() {
        super.onStart();
        pageStarted = true;
        if (viewModel != null) viewModel.resumeTimer();
    }

    /** 页面离开前台时停止计时并尝试同步当前题草稿与进度。 */
    @Override
    public void onStop() {
        pageStarted = false;
        if (viewModel != null) viewModel.pauseTimerAndSave();
        super.onStop();
    }

    /** 页面视图销毁时清理 View 引用，避免 Fragment 重建后误用旧控件。 */
    @Override
    public void onDestroyView() {
        if (answerSheetDialog != null && answerSheetDialog.isShowing()) {
            answerSheetDialog.dismiss();
        }
        answerSheetDialog = null;
        tvTitle = null;
        tvTimer = null;
        tvQuestionIndex = null;
        tvMarkedCount = null;
        tvAnsweredCount = null;
        tvUnansweredCount = null;
        progressBar = null;
        tvProgressPercent = null;
        loadingView = null;
        tvError = null;
        tvQuestionType = null;
        tvScore = null;
        tvQuestionContent = null;
        answerContainer = null;
        explanationCard = null;
        tvResultState = null;
        tvCorrectAnswer = null;
        tvExplanation = null;
        btnMark = null;
        btnAnswerSheet = null;
        btnPrimary = null;
        super.onDestroyView();
    }

    /** 把 XML 中的 ID 绑定到成员字段。 */
    private void bindViews(View root) {
        tvTitle = root.findViewById(R.id.tvQuizTitle);
        tvTimer = root.findViewById(R.id.tvQuizTimer);
        tvQuestionIndex = root.findViewById(R.id.tvQuizQuestionIndex);
        tvMarkedCount = root.findViewById(R.id.tvQuizMarkedCount);
        tvAnsweredCount = root.findViewById(R.id.tvQuizAnsweredCount);
        tvUnansweredCount = root.findViewById(R.id.tvQuizUnansweredCount);
        progressBar = root.findViewById(R.id.progressQuiz);
        tvProgressPercent = root.findViewById(R.id.tvQuizProgressPercent);
        loadingView = root.findViewById(R.id.progressQuizLoading);
        tvError = root.findViewById(R.id.tvQuizError);
        tvQuestionType = root.findViewById(R.id.tvQuizQuestionType);
        tvScore = root.findViewById(R.id.tvQuizScore);
        tvQuestionContent = root.findViewById(R.id.tvQuizQuestionContent);
        answerContainer = root.findViewById(R.id.containerQuizAnswers);
        explanationCard = root.findViewById(R.id.cardQuizExplanation);
        tvResultState = root.findViewById(R.id.tvQuizResultState);
        tvCorrectAnswer = root.findViewById(R.id.tvQuizCorrectAnswer);
        tvExplanation = root.findViewById(R.id.tvQuizExplanation);
        btnMark = root.findViewById(R.id.btnQuizMark);
        btnAnswerSheet = root.findViewById(R.id.btnQuizAnswerSheet);
        btnPrimary = root.findViewById(R.id.btnQuizPrimary);
    }

    /** 创建本页 ViewModel，并复用 ApiClient 提供的 PracticeApiService。 */
    private void initViewModel() {
        ApiClient apiClient = ApiClient.getInstance(requireContext());
        PracticeRepository repository = new PracticeRepository(
                apiClient.getPracticeApiService(), apiClient.getStatisticsApiService());
        QuizTimerStorage timerStorage = new QuizTimerStorage(requireContext().getApplicationContext());
        QuizViewModelFactory factory = new QuizViewModelFactory(repository, timerStorage);
        viewModel = new ViewModelProvider(this, factory).get(QuizViewModel.class);
    }

    /** 注册系统返回监听；用户退出前会得到保存确认，不会误把练习标记成 abandoned。 */
    private void initBackHandler() {
        backPressedCallback = new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                showLeaveConfirm();
            }
        };
        requireActivity().getOnBackPressedDispatcher()
                .addCallback(getViewLifecycleOwner(), backPressedCallback);
    }

    /** 观察 ViewModel 状态，并将状态转换为页面展示。 */
    private void observeViewModel() {
        viewModel.getUiState().observe(getViewLifecycleOwner(), this::render);
    }

    /** 绑定顶部、底部和卡片操作。 */
    private void initListeners(View root) {
        root.findViewById(R.id.btnQuizBack).setOnClickListener(v -> showLeaveConfirm());
        root.findViewById(R.id.btnQuizSettings).setOnClickListener(v -> showSettings());
        tvError.setOnClickListener(v -> {
            QuizUiState current = viewModel.getUiState().getValue();
            if (current == null || current.getDetail() == null) {
                viewModel.loadSession(sessionId);
            }
        });
        btnMark.setOnClickListener(v -> viewModel.toggleCurrentMark());
        btnAnswerSheet.setOnClickListener(v -> showAnswerSheet());
        btnPrimary.setOnClickListener(v -> onPrimaryAction());
    }

    /**
     * 刷新页面固定区域。
     *
     * <p>计时器每秒都会发布一次状态，但本方法仅在题目发生变化或提交状态发生变化时
     * 才重新创建答案控件，避免简答题输入框因计时刷新被重复 setText、光标跳动。</p>
     */
    private void render(QuizUiState state) {
        if (state == null || getView() == null) return;

        loadingView.setVisibility(state.isLoading() ? View.VISIBLE : View.GONE);
        if (state.getErrorMessage() == null || state.getErrorMessage().trim().isEmpty()) {
            tvError.setVisibility(View.GONE);
        } else {
            boolean canRetryLoad = state.getDetail() == null;
            tvError.setText(state.getErrorMessage() + (canRetryLoad ? "（点击重试）" : ""));
            tvError.setClickable(canRetryLoad);
            tvError.setVisibility(View.VISIBLE);
        }

        tvTimer.setText(formatDuration(state.getElapsedMillis()));
        tvTitle.setText(state.getPaperTitle());

        if (state.getDetail() == null || state.getItems().isEmpty()) {
            return;
        }

        // 加载完成且会话尚未完成时，确保页面处于前台的时间开始累计。
        if (pageStarted && !state.isCompleted() && !state.isCompleting()) {
            viewModel.resumeTimer();
        }

        int total = state.getTotalCount();
        int currentOrder = state.getCurrentIndex() + 1;
        int progress = total == 0 ? 0 : Math.round(currentOrder * 100f / total);
        tvQuestionIndex.setText(currentOrder + " / " + total + " 题");
        tvAnsweredCount.setText("已答 " + state.getAnsweredCount());
        tvUnansweredCount.setText("未答 " + state.getUnansweredCount());
        tvMarkedCount.setText("⚑ " + state.getMarkedItemIds().size());
        progressBar.setProgress(progress);
        tvProgressPercent.setText(progress + "%");

        // 只有正常交卷完成态才进入结果页；abandoned 会话仍保留只读答题页。
        // 结果页会一次性加载整卷结果，并在同一个 ScrollView 中纵向展示全部题目。
        if (state.isResultReady()) {
            navigateToResultPage();
            return;
        }

        SessionDetailItem item = state.getCurrentItem();
        if (item == null) return;

        boolean submitted = state.isItemAnswered(item);
        String feedbackSignature = buildFeedbackSignature(item, state);
        boolean needRenderQuestion = renderedItemId != item.getPaperItemId()
                || renderedSubmitted != submitted
                || renderedCompleted != state.isCompleted()
                || renderedSubmitting != state.isSubmitting()
                || renderedCompleting != state.isCompleting()
                || !feedbackSignature.equals(renderedFeedbackSignature);
        if (needRenderQuestion) {
            renderQuestion(item, state);
            renderedItemId = item.getPaperItemId();
            renderedSubmitted = submitted;
            renderedCompleted = state.isCompleted();
            renderedSubmitting = state.isSubmitting();
            renderedCompleting = state.isCompleting();
            renderedFeedbackSignature = feedbackSignature;
        }

        boolean marked = state.isItemMarked(item);
        btnMark.setText(marked ? "⚑ 已标记" : "⚑ 标记");
        btnMark.setTextColor(marked ? COLOR_PRIMARY : COLOR_TEXT);
        btnMark.setEnabled(!state.isMarking() && !state.isCompleted() && !state.isCompleting());
        btnMark.setAlpha(state.isMarking() ? 0.55f : 1f);
        btnAnswerSheet.setEnabled(!state.isCompleting());

        renderPrimaryButton(state, item);
    }

    /** 根据题型名称和题目状态渲染题干、答案区域及提交后的解析。 */
    private void renderQuestion(SessionDetailItem item, QuizUiState state) {
        tvQuestionType.setText(questionTypeName(item.getQuestionType()));
        tvScore.setText(formatScore(item.getScore()) + " 分");
        tvQuestionContent.setText(item.getContent() == null ? "（暂无题干内容）" : item.getContent());
        renderAnswerControls(item, state);
        renderExplanation(item, state);
    }

    /**
     * 按当前 question_type 创建不同答案控件。
     *
     * <p>后端目前固定支持四种题型：</p>
     * <ul>
     *     <li>SINGLE_CHOICE：答案为 String，例如 "A"；</li>
     *     <li>MULTIPLE_CHOICE：答案为 List&lt;String&gt;，例如 ["A", "C"]；</li>
     *     <li>TRUE_FALSE：答案为 Boolean，false 也是合法答案；</li>
     *     <li>SHORT_ANSWER：答案为 String 文本。</li>
     * </ul>
     *
     * <p>以后新增填空、代码等题型时，在此方法增加对应分支，并同步修改 ViewModel 的答案转换规则。</p>
     */
    private void renderAnswerControls(SessionDetailItem item, QuizUiState state) {
        answerContainer.removeAllViews();
        Object answer = state.getAnswer(item.getPaperItemId());
        boolean submitted = state.isItemAnswered(item);
        // 已完成/已放弃的会话进入只读回顾态；即使某道题未作答也不能再编辑。
        boolean answerLocked = submitted || state.isCompleted()
                || state.isSubmitting() || state.isCompleting();

        String questionType = item.getQuestionType();
        if (QuizViewModel.TYPE_SINGLE_CHOICE.equals(questionType)) {
            renderChoiceOptions(item, answer, answerLocked, false);
        } else if (QuizViewModel.TYPE_MULTIPLE_CHOICE.equals(questionType)) {
            renderChoiceOptions(item, answer, answerLocked, true);
        } else if (QuizViewModel.TYPE_TRUE_FALSE.equals(questionType)) {
            renderTrueFalseOptions(answer, answerLocked);
        } else if (QuizViewModel.TYPE_SHORT_ANSWER.equals(questionType)) {
            renderShortAnswer(answer, answerLocked);
        } else {
            // 不认识的题型不伪造一种错误的 JSON 答案；明确提示开发者需要增加对应渲染分支。
            TextView unsupported = new TextView(requireContext());
            unsupported.setText("暂不支持此题型：" + questionType
                    + "\n请在 QuizFragment.renderAnswerControls() 中补充该题型的答案控件。");
            unsupported.setTextColor(COLOR_ERROR);
            unsupported.setTextSize(14);
            unsupported.setPadding(dp(14), dp(16), dp(14), dp(16));
            answerContainer.addView(unsupported);
        }
    }

    /** 渲染单选或多选选项；多选使用相同卡片样式但支持多个 key 同时选中。 */
    private void renderChoiceOptions(SessionDetailItem item, Object answer,
                                     boolean submitted, boolean multiple) {
        List<QuestionOptionInfo> options = item.getOptions();
        if (options == null || options.isEmpty()) {
            addEmptyOptionHint("该题暂时没有可用选项");
            return;
        }

        for (QuestionOptionInfo option : options) {
            if (option == null) continue;
            String key = option.getOptionKey() == null ? "" : option.getOptionKey();
            String content = option.getContent() == null ? "" : option.getContent();
            boolean selected = multiple
                    ? containsAnswer(answer, key)
                    : answer != null && key.equals(String.valueOf(answer));
            View row = createOptionRow(key, content, selected, submitted);
            row.setOnClickListener(v -> {
                if (submitted) return;
                if (multiple) {
                    List<String> next = answerToStringList(viewModel.getUiState().getValue()
                            .getAnswer(item.getPaperItemId()));
                    if (next.contains(key)) next.remove(key);
                    else next.add(key);
                    viewModel.setCurrentAnswer(next);
                } else {
                    viewModel.setCurrentAnswer(key);
                }
                // 选项控件需要立即体现选中状态；不等待网络，也不会重置其他题目状态。
                QuizUiState latest = viewModel.getUiState().getValue();
                if (latest != null) renderAnswerControls(item, latest);
            });
            answerContainer.addView(row, createOptionLayoutParams());
        }
    }

    /** 渲染判断题。后端答案使用 Boolean，而不是把 true/false 作为普通 String 提交。 */
    private void renderTrueFalseOptions(Object answer, boolean submitted) {
        boolean trueSelected = Boolean.TRUE.equals(answer)
                || (answer instanceof String && "true".equalsIgnoreCase((String) answer));
        boolean falseSelected = Boolean.FALSE.equals(answer)
                || (answer instanceof String && "false".equalsIgnoreCase((String) answer));

        View trueRow = createOptionRow("✓", "正确", trueSelected, submitted);
        trueRow.setOnClickListener(v -> {
            if (!submitted) {
                viewModel.setCurrentAnswer(Boolean.TRUE);
                QuizUiState latest = viewModel.getUiState().getValue();
                if (latest != null) renderAnswerControls(viewModel.getUiState().getValue().getCurrentItem(), latest);
            }
        });
        answerContainer.addView(trueRow, createOptionLayoutParams());

        View falseRow = createOptionRow("✕", "错误", falseSelected, submitted);
        falseRow.setOnClickListener(v -> {
            if (!submitted) {
                viewModel.setCurrentAnswer(Boolean.FALSE);
                QuizUiState latest = viewModel.getUiState().getValue();
                if (latest != null) renderAnswerControls(latest.getCurrentItem(), latest);
            }
        });
        answerContainer.addView(falseRow, createOptionLayoutParams());
    }

    /** 渲染简答题多行输入框；答案直接以 String 保存和提交。 */
    private void renderShortAnswer(Object answer, boolean submitted) {
        EditText editText = new EditText(requireContext());
        editText.setTextSize(15);
        editText.setTextColor(COLOR_TEXT);
        editText.setHintTextColor(COLOR_SECONDARY);
        editText.setHint("请输入你的答案…");
        editText.setGravity(Gravity.TOP | Gravity.START);
        editText.setMinHeight(dp(150));
        editText.setPadding(dp(14), dp(13), dp(14), dp(13));
        editText.setBackgroundResource(R.drawable.bg_quiz_option_default);
        editText.setSingleLine(false);
        editText.setInputType(android.text.InputType.TYPE_CLASS_TEXT
                | android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE
                | android.text.InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        editText.setText(answer == null ? "" : String.valueOf(answer));
        editText.setEnabled(!submitted);
        answerContainer.addView(editText, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        if (!submitted) {
            // TextWatcher 仅把内容交给 ViewModel；计时刷新时不会重新创建 EditText。
            editText.addTextChangedListener(new TextWatcher() {
                @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) { }
                @Override public void onTextChanged(CharSequence s, int start, int before, int count) {
                    viewModel.setCurrentAnswer(s == null ? "" : s.toString());
                }
                @Override public void afterTextChanged(Editable s) { }
            });
        }
    }

    /** 创建单个答案选项行，统一处理圆角背景、选中状态、字母圆标和文本样式。 */
    private View createOptionRow(String key, String content, boolean selected,
                                 boolean submitted) {
        LinearLayout row = new LinearLayout(requireContext());
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(13), dp(13), dp(13), dp(13));
        row.setBackground(createRoundedBackground(
                selected ? COLOR_SELECTED_BG : Color.WHITE,
                selected ? COLOR_PRIMARY : COLOR_BORDER,
                selected ? dp(2) : dp(1), dp(15)));
        row.setMinimumHeight(dp(58));
        row.setAlpha(submitted ? 0.95f : 1f);

        TextView symbol = new TextView(requireContext());
        symbol.setGravity(Gravity.CENTER);
        // 多选题也必须保留 A/B/C/D 选项键，选中状态由右侧勾选符号和蓝色背景体现。
        symbol.setText(key);
        symbol.setTextSize(15);
        symbol.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        symbol.setTextColor(selected ? Color.WHITE : COLOR_SECONDARY);
        symbol.setBackground(createRoundedBackground(
                selected ? COLOR_PRIMARY : Color.rgb(245, 247, 252),
                selected ? COLOR_PRIMARY : COLOR_BORDER, dp(1), dp(24)));
        LinearLayout.LayoutParams symbolParams = new LinearLayout.LayoutParams(dp(34), dp(34));
        symbolParams.setMarginEnd(dp(12));
        row.addView(symbol, symbolParams);

        TextView text = new TextView(requireContext());
        text.setText(content);
        text.setTextColor(COLOR_TEXT);
        text.setTextSize(15);
        text.setGravity(Gravity.CENTER_VERTICAL);
        text.setLineSpacing(dp(2), 1f);
        row.addView(text, new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        if (selected) {
            TextView check = new TextView(requireContext());
            check.setText("✓");
            check.setTextColor(COLOR_PRIMARY);
            check.setTextSize(20);
            check.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
            check.setPadding(dp(8), 0, 0, 0);
            row.addView(check);
        }
        return row;
    }

    /** 选项之间使用 12dp 间距，保持各题型视觉一致。 */
    private LinearLayout.LayoutParams createOptionLayoutParams() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.bottomMargin = dp(12);
        return params;
    }

    /** 题型库存数据异常或选项缺失时展示的提示。 */
    private void addEmptyOptionHint(String message) {
        TextView hint = new TextView(requireContext());
        hint.setText(message);
        hint.setTextColor(COLOR_SECONDARY);
        hint.setTextSize(14);
        hint.setPadding(dp(12), dp(15), dp(12), dp(15));
        answerContainer.addView(hint);
    }

    /** 根据当前题的提交状态决定是否显示正确答案和解析。 */
    private void renderExplanation(SessionDetailItem item, QuizUiState state) {
        if (!state.isItemAnswered(item)) {
            explanationCard.setVisibility(View.GONE);
            return;
        }

        SubmitAnswerResponse newResult = state.getSubmitResults().get(item.getPaperItemId());
        Boolean correct = newResult == null ? item.getIsCorrect() : newResult.getIsCorrect();
        String gradingStatus = newResult == null ? item.getGradingStatus() : newResult.getGradingStatus();
        String correctAnswer = newResult == null ? item.getCorrectAnswer() : newResult.getCorrectAnswer();
        String explanation = newResult == null ? item.getExplanation() : newResult.getExplanation();

        if ("ungraded".equals(gradingStatus)) {
            tvResultState.setText("已提交 · 等待人工批改");
            tvResultState.setTextColor(COLOR_CURRENT);
        } else if (Boolean.TRUE.equals(correct)) {
            tvResultState.setText("✓ 回答正确");
            tvResultState.setTextColor(COLOR_SUCCESS);
        } else if (Boolean.FALSE.equals(correct)) {
            tvResultState.setText("✕ 回答错误");
            tvResultState.setTextColor(COLOR_ERROR);
        } else {
            tvResultState.setText("已提交");
            tvResultState.setTextColor(COLOR_PRIMARY);
        }

        tvCorrectAnswer.setText(isBlank(correctAnswer)
                ? "" : "正确答案：" + correctAnswer);
        tvCorrectAnswer.setVisibility(isBlank(correctAnswer) ? View.GONE : View.VISIBLE);
        tvExplanation.setText(isBlank(explanation) ? "暂无答案解析" : "解析：" + explanation);
        explanationCard.setVisibility(View.VISIBLE);
    }

    /**
     * 更新底部主操作按钮。
     *
     * <p>答题过程中，无论当前题有没有选择答案，非最后一题都始终显示“下一题”；
     * 最后一题始终显示“交卷”。答案只保存为草稿，不在切换题目时立即判分。</p>
     */
    private void renderPrimaryButton(QuizUiState state, SessionDetailItem item) {
        if (state.isCompleted()) {
            btnPrimary.setText("返回练习页");
            btnPrimary.setEnabled(true);
            return;
        }

        boolean lastQuestion = state.getCurrentIndex() >= state.getTotalCount() - 1;
        if (state.isCompleting()) {
            btnPrimary.setText("正在提交整卷…");
        } else {
            btnPrimary.setText(lastQuestion ? "交卷" : "下一题  ›");
        }
        btnPrimary.setEnabled(!state.isSubmitting() && !state.isCompleting());
        btnPrimary.setAlpha(btnPrimary.isEnabled() ? 1f : 0.6f);
    }

    /**
     * 处理底部主按钮：普通题只切换到下一题，最后一题才进入整卷交卷确认。
     * 不会因为当前题已经选择答案，就把按钮变成“提交答案”。
     */
    private void onPrimaryAction() {
        QuizUiState state = viewModel.getUiState().getValue();
        if (state == null || state.getCurrentItem() == null) return;
        if (state.isCompleted()) {
            leaveQuizPage();
            return;
        }
        if (state.isSubmitting() || state.isCompleting()) return;

        if (state.getCurrentIndex() < state.getTotalCount() - 1) {
            // moveToQuestion 内部会先保存当前题草稿，再切换题目。
            viewModel.moveToQuestion(state.getCurrentIndex() + 1);
        } else {
            // 最后一题才允许发起整卷交卷，所有答案在此之后统一提交判分。
            showCompleteConfirm();
        }
    }

    /** 交卷完成后跳到独立结果页，结果页会将整份试卷全部题目纵向排列。 */
    private void navigateToResultPage() {
        if (hasNavigatedToResult || !isAdded()) return;
        NavController controller = NavHostFragment.findNavController(this);
        if (controller.getCurrentDestination() == null) return;
        int currentDestinationId = controller.getCurrentDestination().getId();
        boolean openedFromRecords = currentDestinationId == R.id.recordsQuizFragment;
        if (!openedFromRecords && currentDestinationId != R.id.quizFragment) return;

        hasNavigatedToResult = true;
        Bundle args = new Bundle();
        args.putInt(ARG_SESSION_ID, sessionId);
        int popTarget = openedFromRecords ? R.id.recordsQuizFragment : R.id.quizFragment;
        int action = openedFromRecords
                ? R.id.action_recordsQuizFragment_to_recordsQuizResultFragment
                : R.id.action_quizFragment_to_quizResultFragment;
        NavOptions options = new NavOptions.Builder()
                // 从整卷结果页返回时回到打开它的列表/练习入口，不再返回已交卷答题页。
                .setPopUpTo(popTarget, true)
                .build();
        controller.navigate(action, args, options);
    }

    /** 打开答题卡弹窗，显示已答、未答、已标记和当前题。 */
    private void showAnswerSheet() {
        QuizUiState state = viewModel.getUiState().getValue();
        if (state == null || state.getItems().isEmpty()) return;

        LinearLayout content = new LinearLayout(requireContext());
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(8), dp(6), dp(8), dp(6));

        TextView summary = new TextView(requireContext());
        summary.setText("已答 " + state.getAnsweredCount() + " 题    未答 "
                + state.getUnansweredCount() + " 题    标记 "
                + state.getMarkedItemIds().size() + " 题");
        summary.setTextColor(COLOR_SECONDARY);
        summary.setTextSize(13);
        content.addView(summary, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        GridLayout grid = new GridLayout(requireContext());
        grid.setColumnCount(5);
        grid.setUseDefaultMargins(false);
        LinearLayout.LayoutParams gridParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        gridParams.topMargin = dp(16);
        content.addView(grid, gridParams);

        for (int i = 0; i < state.getItems().size(); i++) {
            final int targetIndex = i;
            SessionDetailItem item = state.getItems().get(i);
            boolean answered = state.hasUserAnswer(item);
            boolean current = i == state.getCurrentIndex();
            boolean marked = state.isItemMarked(item);

            TextView number = new TextView(requireContext());
            number.setGravity(Gravity.CENTER);
            number.setText((marked ? "⚑" : "") + (i + 1));
            number.setTextSize(13);
            number.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
            number.setTextColor(current || answered ? Color.WHITE : COLOR_TEXT);

            int fillColor = current ? COLOR_CURRENT
                    : answered ? COLOR_PRIMARY : Color.WHITE;
            int strokeColor = current ? COLOR_CURRENT
                    : answered ? COLOR_PRIMARY : COLOR_BORDER;
            number.setBackground(createRoundedBackground(fillColor, strokeColor, dp(1), dp(24)));

            GridLayout.LayoutParams params = new GridLayout.LayoutParams();
            params.width = 0;
            params.height = dp(44);
            params.columnSpec = GridLayout.spec(GridLayout.UNDEFINED, 1f);
            params.setMargins(dp(4), dp(4), dp(4), dp(8));
            grid.addView(number, params);
            number.setOnClickListener(v -> {
                viewModel.moveToQuestion(targetIndex);
                // 点击题号后收起答题卡，页面由 LiveData 自动切换题目。
                if (answerSheetDialog != null) answerSheetDialog.dismiss();
            });
        }

        ScrollView scrollView = new ScrollView(requireContext());
        scrollView.setFillViewport(false);
        scrollView.addView(content);

        answerSheetDialog = new MaterialAlertDialogBuilder(requireContext())
                .setTitle("答题卡")
                .setView(scrollView)
                .setNegativeButton("关闭", null)
                .setPositiveButton("交卷", null)
                .create();
        answerSheetDialog.setOnShowListener(ignored -> answerSheetDialog
                .getButton(DialogInterface.BUTTON_POSITIVE)
                .setOnClickListener(v -> {
                    answerSheetDialog.dismiss();
                    showCompleteConfirm();
                }));
        answerSheetDialog.setOnDismissListener(ignored -> answerSheetDialog = null);
        answerSheetDialog.show();
    }

    /** 显示交卷二次确认；未答题时会明确展示未答数量。 */
    private void showCompleteConfirm() {
        QuizUiState state = viewModel.getUiState().getValue();
        if (state == null || state.isCompleted() || state.isCompleting()) return;
        String message = state.getUnansweredCount() > 0
                ? "还有 " + state.getUnansweredCount() + " 道题未作答，确定交卷吗？\n交卷后会统一提交已填写答案并判分，未答题目会保留为未作答。"
                : "所有题目都已填写，确定交卷吗？\n交卷后会统一提交整份试卷，并进入包含全部题目、正确答案、你的选择和解析的结果页。";
        new MaterialAlertDialogBuilder(requireContext())
                .setTitle("确认交卷")
                .setMessage(message)
                .setNegativeButton("继续答题", null)
                .setPositiveButton("确认交卷", (dialog, which) -> viewModel.completeSession())
                .show();
    }

    /** 显示保存退出确认；退出只离开页面，不会把会话置为 abandoned。 */
    private void showLeaveConfirm() {
        if (!isAdded()) return;
        QuizUiState currentState = viewModel == null ? null : viewModel.getUiState().getValue();
        if (currentState != null && currentState.isCompleting()) {
            Toast.makeText(requireContext(), "正在提交整份试卷，请等待结果页打开", Toast.LENGTH_SHORT).show();
            return;
        }
        new MaterialAlertDialogBuilder(requireContext())
                .setTitle("暂时退出练习？")
                .setMessage("当前答案会保存为草稿，练习计时会暂停。下次可以从上次进度继续。")
                .setNegativeButton("继续练习", null)
                .setPositiveButton("保存并退出", (dialog, which) -> {
                    pageStarted = false;
                    viewModel.pauseTimerAndSave();
                    leaveQuizPage();
                })
                .show();
    }

    /** 顶部设置入口：提供打开答题卡和保存退出两个常用操作。 */
    private void showSettings() {
        new MaterialAlertDialogBuilder(requireContext())
                .setTitle("练习设置")
                .setItems(new String[]{"查看答题卡", "保存并退出练习"}, (dialog, which) -> {
                    if (which == 0) showAnswerSheet();
                    else showLeaveConfirm();
                })
                .show();
    }

    /** 从刷题页返回当前 Navigation 的上一个目的地。 */
    private void leaveQuizPage() {
        if (!isAdded()) return;
        pageStarted = false;
        NavController controller = NavHostFragment.findNavController(this);
        if (!controller.popBackStack()) {
            // 防御：如果当前页面不是通过 Navigation 栈进入，就返回练习 Tab 根页面。
            controller.navigate(R.id.practiceLandingFragment,
                    null,
                    new NavOptions.Builder()
                            .setPopUpTo(R.id.nav_practice, false)
                            .build());
        }
    }

    /** 根据新提交结果的 answer_record_id 等字段生成签名，判断是否需要重绘解析区域。 */
    private String buildFeedbackSignature(SessionDetailItem item, QuizUiState state) {
        if (item == null) return "";
        SubmitAnswerResponse response = state.getSubmitResults().get(item.getPaperItemId());
        if (response != null) {
            return "new:" + response.getAnswerRecordId() + ":" + response.getGradingStatus();
        }
        return "server:" + item.getStatus() + ":" + item.getGradingStatus()
                + ":" + item.getCorrectAnswer() + ":" + item.getExplanation();
    }

    /** 判断指定答案中是否包含某个选项 key。 */
    private boolean containsAnswer(Object answer, String key) {
        if (answer instanceof List) return ((List<?>) answer).contains(key);
        return answer != null && key.equals(String.valueOf(answer));
    }

    /** 把当前答案安全转换成多选题可编辑的 String List。 */
    private List<String> answerToStringList(Object answer) {
        List<String> result = new ArrayList<>();
        if (answer instanceof List) {
            for (Object item : (List<?>) answer) {
                if (item != null) result.add(String.valueOf(item));
            }
        } else if (answer instanceof String && !((String) answer).trim().isEmpty()) {
            for (String part : ((String) answer).split(",")) {
                if (!part.trim().isEmpty()) result.add(part.trim());
            }
        }
        return result;
    }

    /** 根据题型编码返回中文标签。 */
    private String questionTypeName(String type) {
        if (QuizViewModel.TYPE_SINGLE_CHOICE.equals(type)) return "单选题";
        if (QuizViewModel.TYPE_MULTIPLE_CHOICE.equals(type)) return "多选题";
        if (QuizViewModel.TYPE_TRUE_FALSE.equals(type)) return "判断题";
        if (QuizViewModel.TYPE_SHORT_ANSWER.equals(type)) return "简答题";
        return isBlank(type) ? "题目" : type;
    }

    /** 判断答案是否为空；Boolean.FALSE 不能被当成未作答。 */
    private boolean isEmptyAnswer(Object answer) {
        if (answer == null) return true;
        if (answer instanceof String) return ((String) answer).trim().isEmpty();
        if (answer instanceof List) return ((List<?>) answer).isEmpty();
        return false;
    }

    /** 格式化累计时间为 HH:mm:ss。 */
    private String formatDuration(long millis) {
        long totalSeconds = Math.max(0L, millis / 1000L);
        long hours = totalSeconds / 3600L;
        long minutes = (totalSeconds % 3600L) / 60L;
        long seconds = totalSeconds % 60L;
        return String.format(java.util.Locale.getDefault(), "%02d:%02d:%02d",
                hours, minutes, seconds);
    }

    /** 分值如果是整数则不显示小数点，否则保留最多两位。 */
    private String formatScore(double score) {
        if (Math.abs(score - Math.round(score)) < 0.0001d) {
            return String.valueOf(Math.round(score));
        }
        return String.format(java.util.Locale.getDefault(), "%.2f", score);
    }

    /** 将字符串集合按指定分隔符连接，兼容较低 Android API。 */
    private String join(List<String> values, String separator) {
        StringBuilder builder = new StringBuilder();
        for (String value : values) {
            if (builder.length() > 0) builder.append(separator);
            builder.append(value);
        }
        return builder.toString();
    }

    /** 空白字符串判断。 */
    private boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }

    /** 创建圆角、描边和填充颜色可控的 Drawable，供动态题目选项使用。 */
    private GradientDrawable createRoundedBackground(int fillColor, int strokeColor,
                                                     int strokeWidth, int radius) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(fillColor);
        drawable.setCornerRadius(radius);
        drawable.setStroke(strokeWidth, strokeColor);
        return drawable;
    }

    /** dp 转像素；所有动态控件布局尺寸统一使用 dp。 */
    private int dp(float value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
