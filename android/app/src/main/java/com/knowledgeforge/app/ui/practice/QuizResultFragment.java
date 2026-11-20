package com.knowledgeforge.app.ui.practice;

import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.view.Gravity;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;
import androidx.navigation.NavController;
import androidx.navigation.fragment.NavHostFragment;

import com.knowledgeforge.app.R;
import com.knowledgeforge.app.data.repository.PracticeRepository;
import com.knowledgeforge.app.network.ApiClient;
import com.knowledgeforge.app.network.callback.ApiCallback;
import com.knowledgeforge.app.network.model.ApiException;
import com.knowledgeforge.app.network.model.QuestionOptionInfo;
import com.knowledgeforge.app.network.model.SessionResponse;
import com.knowledgeforge.app.network.model.SessionResultItem;
import com.knowledgeforge.app.network.model.SessionResultResponse;
import com.knowledgeforge.app.network.model.SessionResultSummaryInfo;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * 整卷结果页。
 *
 * <p>与 QuizFragment 的“单题作答”界面分离。此页面只在整份会话完成后打开，
 * 通过 GET /practice/sessions/{session_id}/result 一次读取整卷结果，并把所有题目
 * 按试卷顺序添加到同一个纵向 ScrollView 中，用户向下滑动即可连续查看整张试卷。</p>
 *
 * <p>各题选项颜色规则：</p>
 * <ul>
 *     <li>绿色：标准答案选项；如果用户也选择了该项，会额外标注“你的选择”。</li>
 *     <li>红色：用户选择了该项，但它不是标准答案。</li>
 *     <li>白色：既不是标准答案，也不是用户选择。</li>
 * </ul>
 * 简答题没有选项，因此单独展示用户答案和参考答案。</p>
 */
public class QuizResultFragment extends Fragment {

    /** 接收练习会话 ID 的 Navigation 参数名，与 QuizFragment 保持一致。 */
    public static final String ARG_SESSION_ID = QuizFragment.ARG_SESSION_ID;

    /** 主要蓝色，用于标题、强调数字和主按钮。 */
    private static final int COLOR_PRIMARY = Color.rgb(36, 107, 238);
    /** 页面主要文字颜色。 */
    private static final int COLOR_TEXT = Color.rgb(23, 33, 61);
    /** 次要文字颜色。 */
    private static final int COLOR_SECONDARY = Color.rgb(104, 115, 143);
    /** 选项正常边框色。 */
    private static final int COLOR_BORDER = Color.rgb(220, 228, 244);
    /** 正确答案绿色。 */
    private static final int COLOR_SUCCESS = Color.rgb(22, 166, 117);
    /** 用户错误选择的红色。 */
    private static final int COLOR_ERROR = Color.rgb(226, 86, 93);
    /** 正确答案的浅绿色背景。 */
    private static final int COLOR_SUCCESS_BG = Color.rgb(232, 248, 242);
    /** 错误选择的浅红色背景。 */
    private static final int COLOR_ERROR_BG = Color.rgb(255, 239, 240);
    /** 普通选项的白色背景。 */
    private static final int COLOR_WHITE = Color.WHITE;

    /** 页面加载进度圈。 */
    private ProgressBar loadingView;
    /** 加载失败信息；点击可重新请求整卷结果。 */
    private TextView errorView;
    /** 结果汇总卡片中的得分。 */
    private TextView scoreView;
    /** 本次练习用时。 */
    private TextView durationView;
    /** 正确题数。 */
    private TextView correctCountView;
    /** 错误题数。 */
    private TextView incorrectCountView;
    /** 待人工批改题数。 */
    private TextView ungradedCountView;
    /** 正确率。 */
    private TextView accuracyView;
    /** 放置所有题目卡片的容器；父级位于同一个 ScrollView 中。 */
    private LinearLayout questionsContainer;

    /** 本页要显示的会话 ID。 */
    private int sessionId = -1;
    /** 复用项目已有 PracticeApiService 的数据仓库，不在页面中直接创建 Retrofit 请求。 */
    private PracticeRepository repository;
    /** 防止 Fragment 在网络回调或旋转后重复叠加题目卡片。 */
    private boolean hasRenderedResult;

    /** 创建整卷结果页 XML 布局。 */
    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater,
                             @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_quiz_result, container, false);
    }

    /**
     * 绑定控件、初始化 Repository，并按 Navigation 参数加载整卷结果。
     *
     * @param root 当前 Fragment 的根 View
     * @param savedInstanceState 系统恢复状态；结果数据每次进入页面都从服务器读取
     */
    @Override
    public void onViewCreated(@NonNull View root, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(root, savedInstanceState);
        bindViews(root);

        sessionId = getArguments() == null ? -1 : getArguments().getInt(ARG_SESSION_ID, -1);
        ApiClient client = ApiClient.getInstance(requireContext());
        repository = new PracticeRepository(
                client.getPracticeApiService(), client.getStatisticsApiService());

        root.findViewById(R.id.btnQuizResultBack).setOnClickListener(v -> navigateBack());
        root.findViewById(R.id.btnQuizResultReturn).setOnClickListener(v -> navigateBack());
        errorView.setOnClickListener(v -> loadResult());

        loadResult();
    }

    /** 将结果页 XML 中的固定 View ID 绑定到成员变量。 */
    private void bindViews(View root) {
        loadingView = root.findViewById(R.id.progressQuizResultLoading);
        errorView = root.findViewById(R.id.tvQuizResultError);
        scoreView = root.findViewById(R.id.tvQuizResultScore);
        durationView = root.findViewById(R.id.tvQuizResultDuration);
        correctCountView = root.findViewById(R.id.tvQuizResultCorrectCount);
        incorrectCountView = root.findViewById(R.id.tvQuizResultIncorrectCount);
        ungradedCountView = root.findViewById(R.id.tvQuizResultUngradedCount);
        accuracyView = root.findViewById(R.id.tvQuizResultAccuracy);
        questionsContainer = root.findViewById(R.id.containerQuizResultQuestions);
    }

    /**
     * 请求整卷结果。
     *
     * <p>结果接口只在 completed 会话下返回完整答案投影；此页不使用单题详情接口拼接，
     * 避免漏题或把题目拆成多个页面。</p>
     */
    private void loadResult() {
        if (!isAdded() || repository == null) return;
        if (sessionId <= 0) {
            showError("练习会话编号无效，无法加载结果");
            return;
        }

        hasRenderedResult = false;
        loadingView.setVisibility(View.VISIBLE);
        errorView.setVisibility(View.GONE);
        questionsContainer.removeAllViews();

        repository.getSessionResult(sessionId, new ApiCallback<SessionResultResponse>() {
            @Override
            public void onSuccess(SessionResultResponse response) {
                if (!isAdded() || getView() == null) return;
                loadingView.setVisibility(View.GONE);
                if (response == null || response.getItems() == null) {
                    showError("服务器没有返回试卷题目结果，点击此处重试");
                    return;
                }
                renderResult(response);
            }

            @Override
            public void onError(ApiException error) {
                if (!isAdded() || getView() == null) return;
                loadingView.setVisibility(View.GONE);
                showError(error == null || error.getMessage() == null
                        ? "加载练习结果失败，点击此处重试"
                        : error.getMessage() + "（点击重试）");
            }
        });
    }

    /** 在错误提示中显示服务端错误文本，并允许点击重试。 */
    private void showError(String message) {
        errorView.setText(message);
        errorView.setVisibility(View.VISIBLE);
    }

    /**
     * 渲染顶部成绩摘要和整份试卷所有题目。
     *
     * <p>所有题目卡片都添加到 questionsContainer，而 questionsContainer 位于同一个
     * ScrollView 中，因此结果是一个连续长页面，不会每道题单独切页或弹窗。</p>
     */
    private void renderResult(SessionResultResponse response) {
        if (hasRenderedResult) return;
        hasRenderedResult = true;
        renderSummary(response.getSession(), response.getSummary(), response.getItems().size());

        questionsContainer.removeAllViews();
        // 即使服务端本身已经按题序返回，这里仍显式排序，确保回顾顺序与试卷一致。
        List<SessionResultItem> items = new ArrayList<>(response.getItems());
        Collections.sort(items, Comparator.comparingInt(SessionResultItem::getSortOrder));
        for (int i = 0; i < items.size(); i++) {
            SessionResultItem item = items.get(i);
            if (item == null) continue;
            questionsContainer.addView(createQuestionCard(item, i + 1),
                    createVerticalParams(0, dp(12), 0, 0));
        }

        if (items.isEmpty()) {
            TextView empty = createText("本次练习没有题目结果", 14, COLOR_SECONDARY, false);
            empty.setGravity(Gravity.CENTER);
            empty.setPadding(dp(18), dp(28), dp(18), dp(28));
            questionsContainer.addView(empty);
        }
    }

    /** 设置得分、用时、正确/错误/待批改数量和正确率。 */
    private void renderSummary(SessionResponse session,
                               SessionResultSummaryInfo summary,
                               int itemCount) {
        if (summary == null) {
            scoreView.setText("--");
            correctCountView.setText("0");
            incorrectCountView.setText("0");
            ungradedCountView.setText("0");
            accuracyView.setText("正确率 --");
        } else {
            scoreView.setText(formatScore(summary.getEarnedScore()) + " / "
                    + formatScore(summary.getTotalScore()));
            correctCountView.setText(String.valueOf(summary.getCorrectCount()));
            incorrectCountView.setText(String.valueOf(summary.getIncorrectCount()));
            ungradedCountView.setText(String.valueOf(summary.getUngradedCount()));

            int gradedCount = summary.getCorrectCount() + summary.getIncorrectCount();
            int accuracy = gradedCount <= 0 ? 0
                    : Math.round(summary.getCorrectCount() * 100f / gradedCount);
            accuracyView.setText("正确率 " + accuracy + "%   ·   共 "
                    + summary.getTotalCount() + " 题");
        }

        long duration = session == null || session.getDurationMs() == null
                ? 0L : session.getDurationMs();
        durationView.setText("本次用时 " + formatDuration(duration));
    }

    /**
     * 创建单题结果卡片。
     * 每题卡片包括题号、题型/分值、题干、彩色答案选项、作答状态和紧跟状态的解析。
     */
    private View createQuestionCard(SessionResultItem item, int displayOrder) {
        LinearLayout card = new LinearLayout(requireContext());
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(16), dp(16), dp(16), dp(16));
        card.setBackground(roundBackground(COLOR_WHITE, COLOR_BORDER, dp(16), dp(1)));

        LinearLayout header = new LinearLayout(requireContext());
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setOrientation(LinearLayout.HORIZONTAL);

        TextView number = createText("第 " + displayOrder + " 题", 15, COLOR_PRIMARY, true);
        header.addView(number, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        TextView type = createText(questionTypeName(item.getQuestionType()) + "  ·  "
                + formatScore(item.getScore()) + " 分", 12, COLOR_SECONDARY, false);
        type.setGravity(Gravity.END | Gravity.CENTER_VERTICAL);
        header.addView(type);
        card.addView(header);

        TextView content = createText(item.getContent() == null ? "（暂无题目内容）" : item.getContent(),
                16, COLOR_TEXT, true);
        content.setLineSpacing(dp(4), 1f);
        card.addView(content, createVerticalParams(0, dp(12), 0, 0));

        String questionType = item.getQuestionType() == null
                ? "" : item.getQuestionType().toUpperCase(Locale.ROOT);
        if (QuizViewModel.TYPE_SINGLE_CHOICE.equals(questionType)
                || QuizViewModel.TYPE_MULTIPLE_CHOICE.equals(questionType)) {
            renderChoiceAnswers(card, item);
        } else if (QuizViewModel.TYPE_TRUE_FALSE.equals(questionType)) {
            renderTrueFalseAnswers(card, item);
        } else if (QuizViewModel.TYPE_SHORT_ANSWER.equals(questionType)) {
            // 简答题没有可染色的选项，展示用户答案/参考答案文本。
            addAnswerText(card, "你的答案", formatUserAnswer(item.getYourAnswer()));
            addAnswerText(card, "参考答案", emptyFallback(item.getCorrectAnswer(), "暂无参考答案"));
        } else {
            // 未知题型仍然展示原始答案文本，不把它错误转换成选择题。
            addAnswerText(card, "你的答案", formatUserAnswer(item.getYourAnswer()));
            addAnswerText(card, "正确答案", emptyFallback(item.getCorrectAnswer(), "暂无标准答案"));
        }

        // 正误状态紧跟选项/答案区展示，解析卡片紧接着状态行展示，符合整卷回顾顺序。
        TextView status = createStatusView(item);
        card.addView(status, createVerticalParams(0, dp(14), 0, 0));

        if (!isBlank(item.getExplanation())) {
            TextView explanation = createText("解析：" + item.getExplanation(),
                    13, COLOR_SECONDARY, false);
            explanation.setLineSpacing(dp(3), 1f);
            explanation.setPadding(dp(12), dp(10), dp(12), dp(10));
            explanation.setBackground(roundBackground(Color.rgb(241, 246, 255),
                    Color.TRANSPARENT, dp(10), 0));
            card.addView(explanation, createVerticalParams(0, dp(8), 0, 0));
        }

        return card;
    }

    /** 将选择题选项按标准答案/用户选择标记为绿色或红色。 */
    private void renderChoiceAnswers(LinearLayout card, SessionResultItem item) {
        Set<String> correctKeys = parseAnswerKeys(item.getCorrectAnswer());
        Set<String> userKeys = parseAnswerKeys(item.getYourAnswer());
        // 极少数兼容响应若没有 correct_answer，但判分明确为正确，则用户选择本身就是标准答案。
        if (correctKeys.isEmpty() && Boolean.TRUE.equals(item.getIsCorrect())) {
            correctKeys.addAll(userKeys);
        }
        List<QuestionOptionInfo> options = item.getOptions();

        if (options == null || options.isEmpty()) {
            addAnswerText(card, "你的答案", formatUserAnswer(item.getYourAnswer()));
            addAnswerText(card, "正确答案", emptyFallback(item.getCorrectAnswer(), "暂无标准答案"));
            return;
        }

        TextView legend = createText("绿色：正确答案       红色：你的错误选择", 11, COLOR_SECONDARY, false);
        card.addView(legend, createVerticalParams(0, dp(10), 0, dp(2)));

        for (QuestionOptionInfo option : options) {
            if (option == null) continue;
            String key = option.getOptionKey() == null ? "" : option.getOptionKey().trim();
            boolean correct = correctKeys.contains(normalizeKey(key));
            boolean selected = userKeys.contains(normalizeKey(key));
            String tag;
            if (correct && selected) tag = "✓ 正确 · 你的选择";
            else if (correct) tag = "✓ 正确答案";
            else if (selected) tag = "✕ 你的选择";
            else tag = "";
            card.addView(createOptionResultRow(key, option.getContent(), correct, selected, tag),
                    createVerticalParams(0, dp(7), 0, 0));
        }
    }

    /** 判断题将“正确/错误”作为两个选项，并按标准答案和用户答案分别着色。 */
    private void renderTrueFalseAnswers(LinearLayout card, SessionResultItem item) {
        Set<String> correctKeys = parseAnswerKeys(item.getCorrectAnswer());
        Set<String> userKeys = parseAnswerKeys(item.getYourAnswer());
        if (correctKeys.isEmpty() && Boolean.TRUE.equals(item.getIsCorrect())) {
            correctKeys.addAll(userKeys);
        }

        TextView legend = createText("绿色：正确答案       红色：你的错误选择", 11, COLOR_SECONDARY, false);
        card.addView(legend, createVerticalParams(0, dp(10), 0, dp(2)));

        addTrueFalseRow(card, "true", "正确", correctKeys, userKeys);
        addTrueFalseRow(card, "false", "错误", correctKeys, userKeys);
    }

    /** 创建判断题中的一个候选项行。 */
    private void addTrueFalseRow(LinearLayout parent, String key, String label,
                                 Set<String> correctKeys, Set<String> userKeys) {
        boolean correct = correctKeys.contains(normalizeKey(key));
        boolean selected = userKeys.contains(normalizeKey(key));
        String tag;
        if (correct && selected) tag = "✓ 正确 · 你的选择";
        else if (correct) tag = "✓ 正确答案";
        else if (selected) tag = "✕ 你的选择";
        else tag = "";
        parent.addView(createOptionResultRow(key.equals("true") ? "✓" : "✕",
                        label, correct, selected, tag),
                createVerticalParams(0, dp(7), 0, 0));
    }

    /**
     * 创建彩色选项行。
     *
     * @param key 选项字母/标识
     * @param text 选项具体内容
     * @param isCorrect 是否为标准答案选项
     * @param isSelected 用户是否选择了该项
     * @param tag 右侧状态标签
     */
    private View createOptionResultRow(String key, String text,
                                       boolean isCorrect, boolean isSelected, String tag) {
        int backgroundColor = isCorrect ? COLOR_SUCCESS_BG
                : isSelected ? COLOR_ERROR_BG : COLOR_WHITE;
        int strokeColor = isCorrect ? COLOR_SUCCESS
                : isSelected ? COLOR_ERROR : COLOR_BORDER;
        int textColor = isCorrect ? COLOR_SUCCESS
                : isSelected ? COLOR_ERROR : COLOR_TEXT;

        LinearLayout row = new LinearLayout(requireContext());
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(10), dp(11), dp(10), dp(11));
        row.setBackground(roundBackground(backgroundColor, strokeColor, dp(12), dp(1)));

        TextView keyView = createText(key, 13, Color.WHITE, true);
        keyView.setGravity(Gravity.CENTER);
        keyView.setBackground(roundBackground(isCorrect ? COLOR_SUCCESS
                : isSelected ? COLOR_ERROR : Color.rgb(222, 228, 239),
                Color.TRANSPARENT, dp(18), 0));
        row.addView(keyView, new LinearLayout.LayoutParams(dp(30), dp(30)));

        TextView contentView = createText(text == null ? "" : text, 13, textColor, false);
        contentView.setLineSpacing(dp(2), 1f);
        LinearLayout.LayoutParams contentParams = new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        contentParams.setMargins(dp(10), 0, dp(6), 0);
        row.addView(contentView, contentParams);

        if (!isBlank(tag)) {
            TextView tagView = createText(tag, 10, isCorrect ? COLOR_SUCCESS : COLOR_ERROR, true);
            tagView.setGravity(Gravity.END | Gravity.CENTER_VERTICAL);
            row.addView(tagView, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        }
        return row;
    }

    /** 显示简答题的“你的答案”或“参考答案”文字块。 */
    private void addAnswerText(LinearLayout parent, String label, String value) {
        LinearLayout block = new LinearLayout(requireContext());
        block.setOrientation(LinearLayout.VERTICAL);
        block.setPadding(dp(12), dp(10), dp(12), dp(10));
        block.setBackground(roundBackground(Color.rgb(247, 249, 253), COLOR_BORDER, dp(10), dp(1)));

        TextView labelView = createText(label, 11, COLOR_SECONDARY, true);
        block.addView(labelView);
        TextView valueView = createText(value, 13, COLOR_TEXT, false);
        valueView.setLineSpacing(dp(3), 1f);
        block.addView(valueView, createVerticalParams(0, dp(5), 0, 0));
        parent.addView(block, createVerticalParams(0, dp(8), 0, 0));
    }

    /** 根据判分状态生成“回答正确/回答错误/待批改/未作答”状态行。 */
    private TextView createStatusView(SessionResultItem item) {
        Boolean isCorrect = item.getIsCorrect();
        String status = item.getStatus();
        String gradingStatus = item.getGradingStatus();

        String label;
        int color;
        if ("ungraded".equalsIgnoreCase(gradingStatus)) {
            label = "◷ 已作答 · 待人工批改";
            color = COLOR_PRIMARY;
        } else if (Boolean.TRUE.equals(isCorrect)) {
            label = "✓ 回答正确";
            color = COLOR_SUCCESS;
        } else if (Boolean.FALSE.equals(isCorrect)) {
            label = "✕ 回答错误";
            color = COLOR_ERROR;
        } else if ("answered".equalsIgnoreCase(status)) {
            label = "已作答 · 暂无判分结果";
            color = COLOR_SECONDARY;
        } else {
            label = "未作答";
            color = COLOR_SECONDARY;
        }

        TextView view = createText(label, 14, color, true);
        return view;
    }

    /** 把服务端答案（字符串、字符串数组或 Boolean）转为用于界面比对的选项键集合。 */
    private Set<String> parseAnswerKeys(Object answer) {
        Set<String> keys = new LinkedHashSet<>();
        if (answer == null) return keys;

        if (answer instanceof Boolean) {
            keys.add(Boolean.TRUE.equals(answer) ? "TRUE" : "FALSE");
            return keys;
        }
        if (answer instanceof List) {
            for (Object value : (List<?>) answer) {
                if (value != null) keys.add(normalizeKey(String.valueOf(value)));
            }
            return keys;
        }

        String value = String.valueOf(answer).trim();
        if (value.isEmpty()) return keys;
        if ("true".equalsIgnoreCase(value) || "1".equals(value)) {
            keys.add("TRUE");
            return keys;
        }
        if ("false".equalsIgnoreCase(value) || "0".equals(value)) {
            keys.add("FALSE");
            return keys;
        }

        // 多选题标准答案可能是 "A,C" 或 "[\"A\",\"C\"]"；兼容逗号/顿号/分号/空格。
        value = value.replace("[", "").replace("]", "")
                .replace("\"", "").replace("'", "");
        String[] parts = value.split("[,，、;；\\s]+");
        for (String part : parts) {
            if (!part.trim().isEmpty()) keys.add(normalizeKey(part));
        }
        return keys;
    }

    /** 把选项键统一成大写，避免答案中的大小写差异造成错误着色。 */
    private String normalizeKey(String key) {
        return key == null ? "" : key.trim().toUpperCase(Locale.ROOT);
    }

    /** 把后端多态的用户答案转换为便于阅读的文本。 */
    private String formatUserAnswer(Object answer) {
        if (answer == null) return "未作答";
        if (answer instanceof Boolean) return Boolean.TRUE.equals(answer) ? "正确" : "错误";
        if (answer instanceof List) {
            List<String> values = new ArrayList<>();
            for (Object value : (List<?>) answer) {
                if (value != null) values.add(String.valueOf(value));
            }
            return values.isEmpty() ? "未作答" : join(values, "、");
        }
        String value = String.valueOf(answer).trim();
        if ("true".equalsIgnoreCase(value)) return "正确";
        if ("false".equalsIgnoreCase(value)) return "错误";
        return value.isEmpty() ? "未作答" : value;
    }

    /** 题型编码转换成用户可见中文名称。 */
    private String questionTypeName(String type) {
        if (type == null) return "题目";
        switch (type.toUpperCase(Locale.ROOT)) {
            case QuizViewModel.TYPE_SINGLE_CHOICE: return "单选题";
            case QuizViewModel.TYPE_MULTIPLE_CHOICE: return "多选题";
            case QuizViewModel.TYPE_TRUE_FALSE: return "判断题";
            case QuizViewModel.TYPE_SHORT_ANSWER: return "简答题";
            default: return "其他题型";
        }
    }

    /** 格式化分值，整数不显示小数位。 */
    private String formatScore(double value) {
        if (Math.abs(value - Math.rint(value)) < 0.0001d) return String.valueOf((int) Math.rint(value));
        return String.format(Locale.getDefault(), "%.1f", value);
    }

    /** 将毫秒用时格式化为 HH:mm:ss。 */
    private String formatDuration(long millis) {
        long totalSeconds = Math.max(0L, millis / 1000L);
        long hours = totalSeconds / 3600L;
        long minutes = (totalSeconds % 3600L) / 60L;
        long seconds = totalSeconds % 60L;
        return String.format(Locale.getDefault(), "%02d:%02d:%02d", hours, minutes, seconds);
    }

    /** 合并字符串集合，不依赖 Android 或第三方工具库。 */
    private String join(List<String> values, String separator) {
        StringBuilder builder = new StringBuilder();
        for (String value : values) {
            if (builder.length() > 0) builder.append(separator);
            builder.append(value);
        }
        return builder.toString();
    }

    /** 创建统一字体、字号和颜色的 TextView。 */
    private TextView createText(String text, int sizeSp, int color, boolean bold) {
        TextView view = new TextView(requireContext());
        view.setText(text);
        view.setTextSize(sizeSp);
        view.setTextColor(color);
        if (bold) view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return view;
    }

    /** 创建统一圆角背景；strokeWidth 为 0 时不绘制边框。 */
    private GradientDrawable roundBackground(int fill, int stroke, int radius, int strokeWidth) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(fill);
        drawable.setCornerRadius(radius);
        if (strokeWidth > 0) drawable.setStroke(strokeWidth, stroke);
        return drawable;
    }

    /** 创建带顶部/底部间距的纵向 LayoutParams。 */
    private LinearLayout.LayoutParams createVerticalParams(int left, int top, int right, int bottom) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.setMargins(left, top, right, bottom);
        return params;
    }

    /** 空白字符串判断。 */
    private boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }

    /** 空文本时返回可见的默认说明。 */
    private String emptyFallback(String value, String fallback) {
        return isBlank(value) ? fallback : value;
    }

    /** 将 dp 换算成设备实际像素。 */
    private int dp(float value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    /** 返回练习入口；优先弹出当前结果页，否则导航到练习 Tab 根页面。 */
    private void navigateBack() {
        if (!isAdded()) return;
        NavController controller = NavHostFragment.findNavController(this);
        if (!controller.popBackStack()) {
            // 记录 Tab 中打开的结果页应返回记录列表；练习 Tab 中则返回练习入口。
            if (controller.getCurrentDestination() != null
                    && controller.getCurrentDestination().getId() == R.id.recordsQuizResultFragment) {
                controller.navigate(R.id.recordsFragment);
            } else {
                controller.navigate(R.id.practiceLandingFragment);
            }
        }
    }
}
