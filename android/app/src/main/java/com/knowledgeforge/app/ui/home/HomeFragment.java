package com.knowledgeforge.app.ui.home;

import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.GridLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;
import androidx.lifecycle.ViewModelProvider;
import androidx.core.widget.NestedScrollView;

import com.google.android.material.card.MaterialCardView;
import com.knowledgeforge.app.MainActivity;
import com.knowledgeforge.app.R;
import com.knowledgeforge.app.data.repository.HomeRepository;
import com.knowledgeforge.app.network.ApiClient;
import com.knowledgeforge.app.network.model.HomeDashboardData;
import com.knowledgeforge.app.network.model.PaperListItem;
import com.knowledgeforge.app.network.model.QuestionBank;
import com.knowledgeforge.app.network.model.RecentSessionInfo;
import com.knowledgeforge.app.network.model.SessionListItem;
import com.knowledgeforge.app.network.model.UserInfo;

import java.util.List;
import java.util.Locale;

/**
 * 首页 UI。布局控件只在 Fragment 中渲染，数据由 HomeViewModel 提供。
 */
public class HomeFragment extends Fragment {

    private NestedScrollView scrollView;
    private TextView tvGreeting;
    private TextView tvHomeError;
    private ProgressBar homeLoading;

    private MaterialCardView cardContinue;
    private TextView tvContinueTitle;
    private TextView tvContinueProgress;
    private ProgressBar progressContinue;
    private TextView tvContinuePercent;

    private GridLayout bankGrid;
    private LinearLayout recentContainer;
    private View emptyRecent;

    private HomeViewModel viewModel;

    public HomeFragment() {
        // Required empty public constructor.
    }

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater,
                             @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {
        View root = inflater.inflate(R.layout.fragment_home, container, false);
        bindViews(root);
        initViewModel();
        observeViewModel();
        initListeners(root);
        viewModel.loadIfNeeded();
        return root;
    }

    private void bindViews(View root) {
        scrollView = root.findViewById(R.id.homeScrollView);
        tvGreeting = root.findViewById(R.id.tvGreeting);
        tvHomeError = root.findViewById(R.id.tvHomeError);
        homeLoading = root.findViewById(R.id.homeLoading);

        cardContinue = root.findViewById(R.id.cardContinue);
        tvContinueTitle = root.findViewById(R.id.tvContinueTitle);
        tvContinueProgress = root.findViewById(R.id.tvContinueProgress);
        progressContinue = root.findViewById(R.id.progressContinue);
        tvContinuePercent = root.findViewById(R.id.tvContinuePercent);

        bankGrid = root.findViewById(R.id.bankGrid);
        recentContainer = root.findViewById(R.id.recentContainer);
        emptyRecent = root.findViewById(R.id.emptyRecent);
    }

    private void initViewModel() {
        ApiClient apiClient = ApiClient.getInstance(requireContext());
        HomeRepository repository = new HomeRepository(
                apiClient.getUserApiService(),
                apiClient.getPracticeApiService()
        );

        HomeViewModelFactory factory = new HomeViewModelFactory(repository);
        viewModel = new ViewModelProvider(this, factory).get(HomeViewModel.class);
    }

    private void observeViewModel() {
        viewModel.getUiState().observe(getViewLifecycleOwner(), state -> {
            if (state == null) {
                return;
            }

            homeLoading.setVisibility(state.isLoading() ? View.VISIBLE : View.GONE);

            if (state.getData() != null) {
                render(state.getData());
            }
        });
    }

    private void initListeners(View root) {
        root.findViewById(R.id.btnStartPractice).setOnClickListener(v ->
                navigate(MainActivity.TAB_PRACTICE));

        root.findViewById(R.id.tvViewAllBanks).setOnClickListener(v ->
                navigate(MainActivity.TAB_PRACTICE));

        root.findViewById(R.id.tvViewAllRecords).setOnClickListener(v ->
                navigate(MainActivity.TAB_RECORDS));

        root.findViewById(R.id.btnContinue).setOnClickListener(v ->
                navigate(MainActivity.TAB_RECORDS));

        root.findViewById(R.id.tvProfileShortcut).setOnClickListener(v ->
                navigate(MainActivity.TAB_MINE));

        tvHomeError.setOnClickListener(v -> viewModel.refresh());
    }

    private void render(HomeDashboardData data) {
        renderGreeting(data.getUser());
        renderContinue(data.getActiveSessions(), data.getRecentPapers());
        renderBanks(data.getQuestionBanks());
        renderRecent(data.getRecentPapers());

        if (data.hasErrors()) {
            tvHomeError.setText("部分首页内容暂时无法加载，点击重试");
            tvHomeError.setVisibility(View.VISIBLE);
        } else {
            tvHomeError.setVisibility(View.GONE);
        }
    }

    private void renderGreeting(UserInfo user) {
        String name = null;
        if (user != null) {
            name = user.getNickname();
            if (name == null || name.trim().isEmpty()) {
                name = user.getAccount();
            }
        }

        if (name == null || name.trim().isEmpty()) {
            tvGreeting.setText("欢迎回来");
        } else {
            tvGreeting.setText("欢迎回来，" + name);
        }
    }

    private void renderContinue(List<SessionListItem> sessions,
                                List<PaperListItem> papers) {
        SessionListItem active = null;
        if (sessions != null) {
            for (SessionListItem session : sessions) {
                if (session != null && "in_progress".equals(session.getStatus())) {
                    active = session;
                    break;
                }
            }
        }

        if (active == null) {
            cardContinue.setVisibility(View.GONE);
            return;
        }

        String paperTitle = findPaperTitle(papers, active.getPaperId());
        if (paperTitle == null || paperTitle.trim().isEmpty()) {
            paperTitle = "继续上次练习";
        }

        int total = Math.max(active.getTotalCount(), 0);
        int answered = Math.max(active.getAnsweredCount(), 0);
        int percent = total <= 0 ? 0 : Math.min(100, Math.round(answered * 100f / total));

        tvContinueTitle.setText(paperTitle);
        tvContinueProgress.setText("已完成 " + answered + " / " + total + " 题");
        progressContinue.setMax(100);
        progressContinue.setProgress(percent);
        tvContinuePercent.setText(percent + "%");
        cardContinue.setVisibility(View.VISIBLE);
    }

    private String findPaperTitle(List<PaperListItem> papers, int paperId) {
        if (papers == null) return null;
        for (PaperListItem paper : papers) {
            if (paper != null && paper.getPaperId() == paperId) {
                return paper.getTitle();
            }
        }
        return null;
    }

    private void renderBanks(List<QuestionBank> banks) {
        bankGrid.removeAllViews();

        if (banks == null || banks.isEmpty()) {
            TextView empty = new TextView(requireContext());
            empty.setText("暂无开放题库");
            empty.setTextColor(getResources().getColor(R.color.home_secondary));
            empty.setTextSize(14);
            empty.setPadding(dp(12), dp(16), dp(12), dp(16));
            bankGrid.addView(empty);
            return;
        }

        LayoutInflater inflater = LayoutInflater.from(requireContext());
        LinearLayout row = null;

        for (int i = 0; i < Math.min(banks.size(), 4); i++) {
            if (i % 2 == 0) {
                row = new LinearLayout(requireContext());
                row.setOrientation(LinearLayout.HORIZONTAL);
                GridLayout.LayoutParams rowParams = new GridLayout.LayoutParams();
                rowParams.width = GridLayout.LayoutParams.MATCH_PARENT;
                rowParams.height = GridLayout.LayoutParams.WRAP_CONTENT;
                rowParams.columnSpec = GridLayout.spec(GridLayout.UNDEFINED);
                rowParams.setMargins(0, 0, 0, dp(10));
                bankGrid.addView(row, rowParams);
            }

            QuestionBank bank = banks.get(i);
            View item = inflater.inflate(R.layout.item_home_bank, bankGrid, false);
            TextView name = item.findViewById(R.id.tvBankName);
            TextView count = item.findViewById(R.id.tvBankCount);
            TextView symbol = item.findViewById(R.id.tvBankSymbol);
            TextView arrow = item.findViewById(R.id.tvBankArrow);

            name.setText(bank.getName() == null ? "未命名题库" : bank.getName());
            count.setText(bank.getAvailableQuestionCount() + " 道可练习题");
            symbol.setText(firstCharacter(bank.getName()));

            boolean canAssemble = bank.isCanAssemble();
            item.setAlpha(canAssemble ? 1f : 0.62f);
            if (!canAssemble) {
                count.setText(bank.getUnavailableReason() == null
                        ? "暂无可练习题目" : bank.getUnavailableReason());
                arrow.setVisibility(View.GONE);
            } else {
                item.setOnClickListener(v -> navigate(MainActivity.TAB_PRACTICE));
            }

            LinearLayout.LayoutParams itemParams =
                    new LinearLayout.LayoutParams(0, dp(86), 1f);
            if (i % 2 == 0) {
                itemParams.rightMargin = dp(7);
            } else {
                itemParams.leftMargin = dp(7);
            }
            row.addView(item, itemParams);
        }

        if (banks.size() % 2 == 1 && row != null) {
            View spacer = new View(requireContext());
            row.addView(spacer, new LinearLayout.LayoutParams(0, dp(86), 1f));
        }
    }

    private void renderRecent(List<PaperListItem> papers) {
        recentContainer.removeAllViews();

        if (papers == null || papers.isEmpty()) {
            emptyRecent.setVisibility(View.VISIBLE);
            return;
        }

        emptyRecent.setVisibility(View.GONE);
        PaperListItem paper = papers.get(0);
        View item = LayoutInflater.from(requireContext())
                .inflate(R.layout.item_home_recent, recentContainer, false);

        TextView title = item.findViewById(R.id.tvRecentTitle);
        TextView subtitle = item.findViewById(R.id.tvRecentSubtitle);
        TextView state = item.findViewById(R.id.tvRecentState);

        title.setText(paper.getTitle() == null ? "未命名练习卷" : paper.getTitle());

        RecentSessionInfo recent = paper.getRecentSession();
        String statusText = "尚未练习";
        if (recent != null) {
            if ("in_progress".equals(recent.getStatus())) {
                statusText = "进行中";
            } else if ("completed".equals(recent.getStatus())) {
                statusText = "已完成";
            } else if ("abandoned".equals(recent.getStatus())) {
                statusText = "已放弃";
            }
        }

        subtitle.setText(paper.getQuestionCount() + " 道题 · " + statusText);
        state.setText(statusText);
        item.setOnClickListener(v -> navigate(MainActivity.TAB_RECORDS));
        recentContainer.addView(item);
    }

    private String firstCharacter(String name) {
        if (name == null || name.trim().isEmpty()) return "题";
        return name.trim().substring(0, 1);
    }

    private void navigate(int tabId) {
        if (getActivity() instanceof MainActivity) {
            ((MainActivity) getActivity()).navigateToTab(tabId);
        }
    }

    public void scrollToTop() {
        if (scrollView != null) {
            scrollView.smoothScrollTo(0, 0);
        }
    }

    private int dp(float value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
