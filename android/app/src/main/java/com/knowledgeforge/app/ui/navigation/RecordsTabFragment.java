package com.knowledgeforge.app.ui.navigation;

import android.os.Bundle;
import android.text.TextUtils;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.core.widget.NestedScrollView;
import androidx.core.content.ContextCompat;
import androidx.fragment.app.Fragment;
import androidx.lifecycle.ViewModelProvider;
import androidx.navigation.NavController;
import androidx.navigation.fragment.NavHostFragment;

import com.google.android.material.dialog.MaterialAlertDialogBuilder;
import com.knowledgeforge.app.MainActivity;
import com.knowledgeforge.app.R;
import com.knowledgeforge.app.data.repository.PracticeRepository;
import com.knowledgeforge.app.network.ApiClient;
import com.knowledgeforge.app.network.model.SessionListItem;
import com.knowledgeforge.app.ui.records.RecordsUiState;
import com.knowledgeforge.app.ui.records.RecordsViewModel;
import com.knowledgeforge.app.ui.records.RecordsViewModelFactory;

import java.text.DecimalFormat;
import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * KnowledgeForge「记录」Tab 页面。
 * 页面布局与参考 UI 保持一致：顶部统计卡、横向筛选胶囊、纵向历史记录卡片。
 * 数据来源为 GET /practice/sessions、GET /practice/papers 和 GET /users/me/statistics。
 */
public class RecordsTabFragment extends Fragment {

    /** 筛选项控件 ID：全部。 */
    private TextView tabAll;
    /** 筛选项控件 ID：进行中。 */
    private TextView tabInProgress;
    /** 筛选项控件 ID：已完成。 */
    private TextView tabCompleted;
    /** 筛选项控件 ID：已放弃。 */
    private TextView tabAbandoned;

    /** 包裹整个页面内容的滚动容器。 */
    private NestedScrollView scrollView;
    /** 放置会话卡片的纵向容器。 */
    private LinearLayout recordListContainer;
    /** 列表加载进度条。 */
    private ProgressBar loadingView;
    /** 首次加载失败时可点击重试的提示。 */
    private TextView errorView;
    /** 空列表提示。 */
    private TextView emptyView;
    /** 分页底部状态文案。 */
    private TextView footerView;

    /** 顶部统计：练习总次数。 */
    private TextView totalPracticeView;
    /** 顶部统计：答过的不同题目数。 */
    private TextView totalQuestionsView;
    /** 顶部统计：达到后端样本阈值后的平均正确率。 */
    private TextView averageAccuracyView;

    /** 当前页面的 ViewModel。 */
    private RecordsViewModel viewModel;
    /** 避免视图销毁后继续更新旧控件。 */
    private boolean viewReady;
    /** 跳过首次 onResume；后续从答题/结果子页面返回时刷新会话状态。 */
    private boolean firstResume = true;

    /** 创建练习记录页面 XML。 */
    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater,
                             @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_records, container, false);
    }

    /** 绑定页面控件、初始化 ViewModel、注册筛选和分页事件。 */
    @Override
    public void onViewCreated(@NonNull View root, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(root, savedInstanceState);
        viewReady = true;
        bindViews(root);
        setupToolbar(root);
        setupFilters();
        setupPagination();
        setupViewModel();
    }

    /** 将 XML 中的控件 ID 绑定到 Fragment 成员变量。 */
    private void bindViews(View root) {
        scrollView = root.findViewById(R.id.scrollRecords);
        recordListContainer = root.findViewById(R.id.containerRecordsList);
        loadingView = root.findViewById(R.id.progressRecordsLoading);
        errorView = root.findViewById(R.id.tvRecordsError);
        emptyView = root.findViewById(R.id.tvRecordsEmpty);
        footerView = root.findViewById(R.id.tvRecordsFooter);

        totalPracticeView = root.findViewById(R.id.tvRecordsTotalPractice);
        totalQuestionsView = root.findViewById(R.id.tvRecordsTotalQuestions);
        averageAccuracyView = root.findViewById(R.id.tvRecordsAverageAccuracy);

        tabAll = root.findViewById(R.id.tabRecordsAll);
        tabInProgress = root.findViewById(R.id.tabRecordsInProgress);
        tabCompleted = root.findViewById(R.id.tabRecordsCompleted);
        tabAbandoned = root.findViewById(R.id.tabRecordsAbandoned);
    }

    /** 设置顶部返回和右侧清理图标。 */
    private void setupToolbar(View root) {
        root.findViewById(R.id.btnRecordsBack).setOnClickListener(v -> {
            if (getActivity() instanceof MainActivity) {
                ((MainActivity) getActivity()).navigateToTab(MainActivity.TAB_HOME);
            }
        });

        // 当前 PracticeApiService 没有删除会话/答题历史的接口。
        // 不能把“归档试卷”错误当成“删除会话”；这里保留参考图的入口并如实说明能力边界。
        root.findViewById(R.id.btnRecordsClear).setOnClickListener(v ->
                new MaterialAlertDialogBuilder(requireContext())
                        .setTitle("管理练习记录")
                        .setMessage("历史记录由服务器按练习会话保存。目前接口不支持删除练习记录，归档试卷也不会删除历史成绩。")
                        .setPositiveButton("知道了", null)
                        .show());

        errorView.setOnClickListener(v -> {
            if (viewModel != null) viewModel.refresh();
        });
    }

    /** 将四个胶囊筛选项映射到后端真实支持的会话状态。 */
    private void setupFilters() {
        tabAll.setOnClickListener(v -> selectFilter(null));
        tabInProgress.setOnClickListener(v -> selectFilter("in_progress"));
        tabCompleted.setOnClickListener(v -> selectFilter("completed"));
        tabAbandoned.setOnClickListener(v -> selectFilter("abandoned"));
    }

    /** 在 NestedScrollView 接近底部时触发下一页加载。 */
    private void setupPagination() {
        scrollView.setOnScrollChangeListener((NestedScrollView.OnScrollChangeListener)
                (v, scrollX, scrollY, oldScrollX, oldScrollY) -> {
                    if (viewModel == null || v.getChildCount() == 0) return;
                    View child = v.getChildAt(0);
                    int remaining = child.getBottom() - (scrollY + v.getHeight());
                    if (remaining < dp(240)) viewModel.loadMore();
                });
    }

    /** 创建 Repository 和 ViewModel，观察数据变化。 */
    private void setupViewModel() {
        ApiClient client = ApiClient.getInstance(requireContext().getApplicationContext());
        PracticeRepository repository = new PracticeRepository(
                client.getPracticeApiService(), client.getStatisticsApiService());
        RecordsViewModelFactory factory = new RecordsViewModelFactory(repository);
        viewModel = new ViewModelProvider(this, factory).get(RecordsViewModel.class);

        viewModel.getUiState().observe(getViewLifecycleOwner(), this::renderState);
        viewModel.loadIfNeeded();
    }

    /** 响应用户筛选。 */
    private void selectFilter(String status) {
        if (viewModel != null) viewModel.selectStatus(status);
    }

    /** 将 ViewModel 当前状态同步到统计卡、筛选按钮和列表。 */
    private void renderState(RecordsUiState state) {
        if (!viewReady || state == null || getView() == null) return;

        renderStatistics(state);
        renderFilterSelection(state.getSelectedStatus());

        loadingView.setVisibility(state.isLoading() ? View.VISIBLE : View.GONE);
        errorView.setVisibility(TextUtils.isEmpty(state.getErrorMessage())
                ? View.GONE : View.VISIBLE);
        if (!TextUtils.isEmpty(state.getErrorMessage())) {
            errorView.setText(state.getErrorMessage() + "（点击重试）");
        }

        renderRecords(state);
    }

    /** 更新顶部三项汇总数字。 */
    private void renderStatistics(RecordsUiState state) {
        totalPracticeView.setText(formatInteger(state.getTotalPracticeCount()) + " 次");
        totalQuestionsView.setText(formatInteger(state.getTotalAnsweredQuestions()) + " 题");

        Double accuracy = state.getAverageAccuracy();
        if (accuracy == null) {
            averageAccuracyView.setText("样本不足");
        } else {
            averageAccuracyView.setText(String.format(Locale.getDefault(), "%.1f%%",
                    Math.max(0d, Math.min(1d, accuracy)) * 100d));
        }
    }

    /** 更新四个状态筛选胶囊的选中样式。 */
    private void renderFilterSelection(String status) {
        setTabSelected(tabAll, status == null);
        setTabSelected(tabInProgress, "in_progress".equals(status));
        setTabSelected(tabCompleted, "completed".equals(status));
        setTabSelected(tabAbandoned, "abandoned".equals(status));
    }

    /** 设置一个筛选胶囊是否处于蓝色选中状态。 */
    private void setTabSelected(TextView tab, boolean selected) {
        tab.setSelected(selected);
        tab.setTextColor(ContextCompat.getColor(requireContext(),
                selected ? R.color.records_white : R.color.records_text));
        tab.setBackgroundResource(selected
                ? R.drawable.bg_records_tab_selected
                : R.drawable.bg_records_tab_normal);
    }

    /** 根据当前分页数据绘制记录卡片和底部状态。 */
    private void renderRecords(RecordsUiState state) {
        recordListContainer.removeAllViews();
        emptyView.setVisibility(View.GONE);

        if (state.getSessions().isEmpty()) {
            if (!state.isLoading() && TextUtils.isEmpty(state.getErrorMessage())) {
                emptyView.setVisibility(View.VISIBLE);
                emptyView.setText("暂无练习记录\n完成一次练习后，记录会显示在这里");
            }
        } else {
            LayoutInflater inflater = LayoutInflater.from(requireContext());
            for (SessionListItem session : state.getSessions()) {
                if (session == null) continue;
                View item = inflater.inflate(R.layout.item_practice_record,
                        recordListContainer, false);
                bindRecordItem(item, session, state);
                recordListContainer.addView(item);
            }
        }

        if (state.isLoadingMore()) {
            footerView.setVisibility(View.VISIBLE);
            footerView.setText("正在加载更多记录…");
        } else if (!state.getSessions().isEmpty() && !state.hasMore()) {
            footerView.setVisibility(View.VISIBLE);
            footerView.setText("────────  没有更多记录了  ────────");
        } else if (state.hasMore() && !state.isLoading()
                && !(state.getSessions().isEmpty() && !TextUtils.isEmpty(state.getErrorMessage()))) {
            footerView.setVisibility(View.VISIBLE);
            footerView.setText("向下滑动加载更多");
        } else {
            footerView.setVisibility(View.GONE);
        }
    }

    /** 把单个会话字段绑定到列表卡片。 */
    private void bindRecordItem(View item, SessionListItem session, RecordsUiState state) {
        TextView titleView = item.findViewById(R.id.tvRecordTitle);
        TextView durationView = item.findViewById(R.id.tvRecordDuration);
        TextView dateView = item.findViewById(R.id.tvRecordDate);
        TextView metricView = item.findViewById(R.id.tvRecordMetric);
        TextView metricLabelView = item.findViewById(R.id.tvRecordMetricLabel);
        TextView statusView = item.findViewById(R.id.tvRecordStatus);
        TextView iconView = item.findViewById(R.id.tvRecordIcon);
        View iconContainer = item.findViewById(R.id.recordIconContainer);

        String title = state.getPaperTitle(session.getPaperId());
        titleView.setText(TextUtils.isEmpty(title) ? "练习试卷 #" + session.getPaperId() : title);

        String status = session.getStatus();
        String dateText = formatDate(selectSessionDate(session));
        dateView.setText(TextUtils.isEmpty(dateText) ? "时间暂不可用" : dateText);

        if ("in_progress".equals(status)) {
            durationView.setText("已答 " + session.getAnsweredCount() + "/"
                    + session.getTotalCount() + " 题");
            metricView.setText("继续");
            metricLabelView.setText("练习中");
            statusView.setText("进行中");
            statusView.setVisibility(View.VISIBLE);
            iconView.setText("▸");
            iconContainer.setBackgroundResource(R.drawable.bg_records_icon_lavender);
            metricView.setTextColor(ContextCompat.getColor(requireContext(), R.color.records_primary));
            item.setOnClickListener(v -> openSession(session));
        } else if ("completed".equals(status)) {
            Long duration = session.getDurationMs();
            durationView.setText(duration == null ? "用时：--" : "用时：" + formatDuration(duration));
            int graded = session.getCorrectCount() + session.getIncorrectCount();
            if (graded > 0) {
                int rate = Math.round(session.getCorrectCount() * 100f / graded);
                metricView.setText(rate + "%");
                metricLabelView.setText("正确率");
            } else {
                metricView.setText("待批改");
                metricLabelView.setText("正确率");
            }
            statusView.setText("已完成");
            statusView.setVisibility(View.VISIBLE);
            iconView.setText("▤");
            iconContainer.setBackgroundResource(R.drawable.bg_records_icon_blue);
            metricView.setTextColor(ContextCompat.getColor(requireContext(), R.color.records_primary));
            item.setOnClickListener(v -> openSession(session));
        } else {
            Long duration = session.getDurationMs();
            durationView.setText(duration == null ? "已答 " + session.getAnsweredCount()
                    + "/" + session.getTotalCount() + " 题" : "用时：" + formatDuration(duration));
            metricView.setText("已放弃");
            metricLabelView.setText("练习状态");
            statusView.setText("已放弃");
            statusView.setVisibility(View.VISIBLE);
            iconView.setText("!");
            iconContainer.setBackgroundResource(R.drawable.bg_records_icon_orange);
            metricView.setTextColor(ContextCompat.getColor(requireContext(), R.color.records_warning));
            item.setOnClickListener(v -> Toast.makeText(requireContext(),
                    "已放弃的练习暂不支持查看整卷解析", Toast.LENGTH_SHORT).show());
        }
    }

    /** 进行中的会话进入答题页；已完成的会话进入整卷滚动结果页。 */
    private void openSession(SessionListItem session) {
        if (!isAdded() || session == null) return;
        Bundle args = new Bundle();
        args.putInt("session_id", session.getSessionId());
        NavController controller = NavHostFragment.findNavController(this);

        if ("in_progress".equals(session.getStatus())) {
            controller.navigate(R.id.action_recordsFragment_to_recordsQuizFragment, args);
        } else if ("completed".equals(session.getStatus())) {
            controller.navigate(R.id.action_recordsFragment_to_recordsQuizResultFragment, args);
        }
    }

    /** 获取会话最适合展示的时间：完成时间、最后活跃时间、放弃时间或开始时间。 */
    private String selectSessionDate(SessionListItem session) {
        if ("completed".equals(session.getStatus()) && !TextUtils.isEmpty(session.getCompletedAt())) {
            return session.getCompletedAt();
        }
        if ("abandoned".equals(session.getStatus()) && !TextUtils.isEmpty(session.getAbandonedAt())) {
            return session.getAbandonedAt();
        }
        if (!TextUtils.isEmpty(session.getLastActiveAt())) return session.getLastActiveAt();
        return session.getStartedAt();
    }

    /** 将后端毫秒时长格式化为 HH:mm:ss。 */
    private String formatDuration(Long durationMs) {
        long seconds = Math.max(0L, durationMs == null ? 0L : durationMs / 1000L);
        long hours = seconds / 3600L;
        long minutes = (seconds % 3600L) / 60L;
        long remainSeconds = seconds % 60L;
        return String.format(Locale.getDefault(), "%02d:%02d:%02d", hours, minutes, remainSeconds);
    }

    /**
     * 把 ISO-8601 时间转成当前设备本地时间 yyyy-MM-dd HH:mm。
     * 兼容后端可能返回的毫秒、Z 后缀以及 +08:00 这类偏移格式。
     */
    private String formatDate(String raw) {
        if (TextUtils.isEmpty(raw)) return "";
        String value = raw.trim();
        String normalized = value;
        if (normalized.endsWith("Z")) {
            normalized = normalized.substring(0, normalized.length() - 1) + "+0000";
        } else if (normalized.matches(".*[+-]\\d{2}:\\d{2}$")) {
            normalized = normalized.substring(0, normalized.length() - 3)
                    + normalized.substring(normalized.length() - 2);
        }

        String[] patterns = new String[]{
                "yyyy-MM-dd'T'HH:mm:ss.SSSZ",
                "yyyy-MM-dd'T'HH:mm:ssZ",
                "yyyy-MM-dd'T'HH:mm:ss.SSS",
                "yyyy-MM-dd'T'HH:mm:ss"
        };
        for (String pattern : patterns) {
            SimpleDateFormat parser = new SimpleDateFormat(pattern, Locale.US);
            parser.setLenient(false);
            try {
                Date date = parser.parse(normalized);
                if (date != null) {
                    return new SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault()).format(date);
                }
            } catch (ParseException ignored) {
                // 尝试下一种 ISO 时间格式。
            }
        }
        // 后端格式不符合已知模式时，至少不要把原始时间隐藏掉。
        return value.replace('T', ' ').replace("Z", "");
    }

    /** 格式化整数，加入千位分隔符以贴近设计稿。 */
    private String formatInteger(int value) {
        return new DecimalFormat("#,##0").format(Math.max(0, value));
    }

    /** 将 dp 换算为当前设备像素。 */
    private int dp(float value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    /** 供 MainActivity 重复点击记录 Tab 时回到页面顶部。 */
    public void scrollToTop() {
        if (scrollView != null) scrollView.smoothScrollTo(0, 0);
    }

    @Override
    public void onResume() {
        super.onResume();
        // 首次进入已经在 setupViewModel() 中加载；从答题页/结果页返回时刷新最新状态。
        if (firstResume) {
            firstResume = false;
        } else if (viewModel != null) {
            viewModel.refresh();
        }
    }

    @Override
    public void onDestroyView() {
        viewReady = false;
        scrollView = null;
        recordListContainer = null;
        super.onDestroyView();
    }
}
