package com.knowledgeforge.app.ui.practice;

import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;
import androidx.lifecycle.ViewModelProvider;
import androidx.core.widget.NestedScrollView;

import com.google.android.material.dialog.MaterialAlertDialogBuilder;
import com.knowledgeforge.app.MainActivity;
import com.knowledgeforge.app.R;
import com.knowledgeforge.app.data.repository.PracticeRepository;
import com.knowledgeforge.app.network.ApiClient;
import com.knowledgeforge.app.network.callback.ApiCallback;
import com.knowledgeforge.app.network.model.ApiException;
import com.knowledgeforge.app.network.model.PageResponse;
import com.knowledgeforge.app.network.model.PaperListItem;
import com.knowledgeforge.app.network.model.PracticeLandingData;
import com.knowledgeforge.app.network.model.QuestionBank;
import com.knowledgeforge.app.network.model.SessionListItem;
import com.knowledgeforge.app.network.model.SessionResponse;
import com.knowledgeforge.app.network.model.UserAnswerSummary;
import com.knowledgeforge.app.network.model.UserPracticeSummary;
import com.knowledgeforge.app.network.model.UserStatisticsResponse;

import java.util.List;
import java.util.Map;

/** 练习入口页：继续练习、自定义组卷、开放题库和真实学习统计。 */
public class PracticeLandingFragment extends Fragment {

    private NestedScrollView scrollView;
    private ProgressBar loading;
    private TextView errorText;
    private View  continueCard;
    private TextView continueTitle;
    private TextView continueProgress;
    private TextView continuePercent;
    private ProgressBar continueProgressBar;
    private LinearLayout bankContainer;
    private TextView emptyBanks;
    private TextView expandBanks;
    private TextView accuracyValue;
    private TextView answeredValue;
    private TextView sessionValue;
    private TextView retryText;

    private PracticeLandingViewModel viewModel;
    private PracticeRepository repository;
    private boolean showAllBanks;
    private SessionListItem activeSession;

    public PracticeLandingFragment() { }

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater,
                             @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_practice, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View root, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(root, savedInstanceState);
        bindViews(root);
        initViewModel();
        observeViewModel();
        initListeners(root);
        viewModel.loadIfNeeded();
    }

    private void bindViews(View root) {
        scrollView = root.findViewById(R.id.practiceScrollView);
        loading = root.findViewById(R.id.practiceLoading);
        errorText = root.findViewById(R.id.practiceError);
        continueCard = root.findViewById(R.id.cardContinuePractice);
        continueTitle = root.findViewById(R.id.tvContinuePracticeTitle);
        continueProgress = root.findViewById(R.id.tvContinuePracticeProgress);
        continuePercent = root.findViewById(R.id.tvContinuePracticePercent);
        continueProgressBar = root.findViewById(R.id.progressContinuePractice);
        bankContainer = root.findViewById(R.id.practiceBankContainer);
        emptyBanks = root.findViewById(R.id.tvPracticeEmptyBanks);
        expandBanks = root.findViewById(R.id.tvPracticeExpandBanks);
        accuracyValue = root.findViewById(R.id.tvPracticeAccuracy);
        answeredValue = root.findViewById(R.id.tvPracticeAnswered);
        sessionValue = root.findViewById(R.id.tvPracticeSessionTotal);
        retryText = root.findViewById(R.id.tvPracticeRetry);
        retryText.setVisibility(View.GONE);
    }

    private void initViewModel() {
        ApiClient apiClient = ApiClient.getInstance(requireContext());
        repository = new PracticeRepository(
                apiClient.getPracticeApiService(), apiClient.getStatisticsApiService());
        PracticeLandingViewModelFactory factory = new PracticeLandingViewModelFactory(repository);
        viewModel = new ViewModelProvider(this, factory).get(PracticeLandingViewModel.class);
    }

    private void observeViewModel() {
        viewModel.getUiState().observe(getViewLifecycleOwner(), state -> {
            if (state == null) return;
            loading.setVisibility(state.isLoading() ? View.VISIBLE : View.GONE);
            if (state.isLoading()) {
                errorText.setVisibility(View.GONE);
            }
            if (state.getData() != null) {
                render(state.getData());
            } else if (state.getErrorMessage() != null) {
                errorText.setText(state.getErrorMessage());
                errorText.setVisibility(View.VISIBLE);
            }
        });
    }

    private void initListeners(View root) {
        // 整张自定义组卷卡片均可点击；按钮本身保留相同动作。
        root.findViewById(R.id.cardCreateCustomPaper).setOnClickListener(v -> openAssemble(-1));
        root.findViewById(R.id.btnCreateCustomPaper).setOnClickListener(v -> openAssemble(-1));
        root.findViewById(R.id.tvPracticeExpandBanks).setOnClickListener(v -> {
            showAllBanks = !showAllBanks;
            PracticeLandingUiState state = viewModel.getUiState().getValue();
            if (state != null && state.getData() != null) renderBanks(state.getData().getQuestionBanks());
        });
        retryText.setOnClickListener(v -> viewModel.refresh());
        root.findViewById(R.id.cardLearningData).setOnClickListener(v -> {
            if (getActivity() instanceof MainActivity) {
                ((MainActivity) getActivity()).navigateToTab(MainActivity.TAB_MINE);
            }
        });
        continueCard.setOnClickListener(v -> resumeCurrentSession());
        root.findViewById(R.id.btnContinuePractice).setOnClickListener(v -> resumeCurrentSession());
    }

    private void render(PracticeLandingData data) {
        errorText.setVisibility(View.GONE);
        if (data.hasErrors()) {
            errorText.setText("部分内容暂时无法加载");
            errorText.setVisibility(View.VISIBLE);
            retryText.setVisibility(View.VISIBLE);
        } else {
            retryText.setVisibility(View.GONE);
        }
        renderContinue(data.getActiveSessions(), data.getPapers());
        renderBanks(data.getQuestionBanks());
        renderStatistics(data.getStatistics());
    }

    private void renderContinue(List<SessionListItem> sessions, List<PaperListItem> papers) {
        activeSession = null;
        if (sessions != null) {
            for (SessionListItem item : sessions) {
                if (item != null && "in_progress".equals(item.getStatus())) {
                    activeSession = item;
                    break;
                }
            }
        }
        if (activeSession == null) {
            continueCard.setVisibility(View.GONE);
            return;
        }
        String title = findPaperTitle(papers, activeSession.getPaperId());
        if (title == null || title.trim().isEmpty()) title = "继续上次练习";
        int total = Math.max(0, activeSession.getTotalCount());
        int answered = Math.max(0, activeSession.getAnsweredCount());
        int percent = total == 0 ? 0 : Math.min(100, Math.round(answered * 100f / total));
        continueTitle.setText(title);
        continueProgress.setText("已答 " + answered + " / " + total + " 题");
        continueProgressBar.setMax(100);
        continueProgressBar.setProgress(percent);
        continuePercent.setText(percent + "%");
        continueCard.setVisibility(View.VISIBLE);
    }

    private String findPaperTitle(List<PaperListItem> papers, int paperId) {
        if (papers == null) return null;
        for (PaperListItem paper : papers) {
            if (paper != null && paper.getPaperId() == paperId) return paper.getTitle();
        }
        return null;
    }

    private void renderBanks(List<QuestionBank> banks) {
        bankContainer.removeAllViews();
        if (banks == null || banks.isEmpty()) {
            emptyBanks.setVisibility(View.VISIBLE);
            expandBanks.setVisibility(View.GONE);
            return;
        }
        emptyBanks.setVisibility(View.GONE);
        int displayCount = showAllBanks ? banks.size() : Math.min(3, banks.size());
        expandBanks.setVisibility(banks.size() > 3 ? View.VISIBLE : View.GONE);
        expandBanks.setText(showAllBanks ? "收起  ˄" : "展开更多  ›");

        LayoutInflater inflater = LayoutInflater.from(requireContext());
        for (int i = 0; i < displayCount; i++) {
            QuestionBank bank = banks.get(i);
            if (bank == null) continue;
            View item = inflater.inflate(R.layout.item_practice_bank, bankContainer, false);
            TextView icon = item.findViewById(R.id.tvPracticeBankIcon);
            TextView name = item.findViewById(R.id.tvPracticeBankName);
            TextView count = item.findViewById(R.id.tvPracticeBankCount);
            TextView details = item.findViewById(R.id.tvPracticeBankTypes);
            TextView action = item.findViewById(R.id.tvPracticeBankAction);

            name.setText(bank.getName() == null ? "未命名题库" : bank.getName());
            icon.setText(firstCharacter(bank.getName()));
            count.setText("共 " + bank.getAvailableQuestionCount() + " 道可练习题");
            details.setText(typeSummary(bank.getQuestionTypeCounts()));

            boolean canAssemble = bank.isCanAssemble();
            item.setAlpha(canAssemble ? 1f : 0.62f);
            action.setText(canAssemble ? "去组卷  ›" : "暂不可练");
            if (canAssemble) item.setOnClickListener(v -> openAssemble(bank.getId()));
            else item.setOnClickListener(v -> Toast.makeText(requireContext(),
                    bank.getUnavailableReason() == null ? "该题库暂无可练习题目" : bank.getUnavailableReason(),
                    Toast.LENGTH_SHORT).show());
            bankContainer.addView(item);
        }
    }

    private String typeSummary(Map<String, Integer> counts) {
        if (counts == null || counts.isEmpty()) return "题型库存以组卷配置页为准";
        return "单选 " + mapCount(counts, "SINGLE_CHOICE")
                + " · 多选 " + mapCount(counts, "MULTIPLE_CHOICE")
                + " · 判断 " + mapCount(counts, "TRUE_FALSE")
                + " · 简答 " + mapCount(counts, "SHORT_ANSWER");
    }

    private int mapCount(Map<String, Integer> values, String key) {
        if (values == null) return 0;
        Integer count = values.get(key);
        if (count == null) count = values.get(key.toLowerCase());
        return count == null ? 0 : count;
    }

    private void renderStatistics(UserStatisticsResponse statistics) {
        if (statistics == null) {
            accuracyValue.setText("--");
            answeredValue.setText("--");
            sessionValue.setText("--");
            return;
        }
        UserAnswerSummary answer = statistics.getAnswerSummary();
        UserPracticeSummary practice = statistics.getPracticeSummary();
        if (answer != null && answer.getAccuracy() != null) {
            accuracyValue.setText(Math.round(answer.getAccuracy() * 100) + "%");
        } else {
            accuracyValue.setText("样本不足");
        }
        answeredValue.setText(answer == null ? "--" : String.valueOf(answer.getAnsweredQuestionCount()));
        sessionValue.setText(practice == null ? "--" : String.valueOf(practice.getSessionTotal()));
    }

    private void resumeCurrentSession() {
        if (activeSession == null || repository == null) return;
        // 固定本次点击对应的会话，避免请求返回前刷新列表导致 activeSession 被替换。
        final SessionListItem targetSession = activeSession;
        setContinueEnabled(false);
        repository.resumeSession(targetSession.getSessionId(), new ApiCallback<SessionResponse>() {
            @Override
            public void onSuccess(SessionResponse result) {
                if (!isAdded()) return;
                setContinueEnabled(true);
                int current = result == null ? targetSession.getCurrentItemOrder() : result.getCurrentItemOrder();
                new MaterialAlertDialogBuilder(requireContext())
                        .setTitle("练习会话已恢复")
                        .setMessage("会话已成功恢复，将从第 " + current + " 题继续。\n\n答题界面将在下一步接入。")
                        .setPositiveButton("知道了", null)
                        .show();
            }

            @Override
            public void onError(ApiException error) {
                if (!isAdded()) return;
                setContinueEnabled(true);
                Toast.makeText(requireContext(), error == null ? "恢复失败" : error.getMessage(),
                        Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void setContinueEnabled(boolean enabled) {
        if (continueCard != null) continueCard.setEnabled(enabled);
        View button = getView() == null ? null : getView().findViewById(R.id.btnContinuePractice);
        if (button != null) button.setEnabled(enabled);
    }

    private String firstCharacter(String value) {
        if (value == null || value.trim().isEmpty()) return "题";
        return value.trim().substring(0, 1);
    }

    private void openAssemble(int bankId) {
        Fragment parent = getParentFragment();
        if (parent instanceof PracticeFragment) {
            ((PracticeFragment) parent).openAssemble(bankId);
        }
    }

    public void scrollToTop() {
        if (scrollView != null) scrollView.smoothScrollTo(0, 0);
    }

    public void refreshData() {
        if (viewModel != null) viewModel.refresh();
    }

    private int dp(float value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
