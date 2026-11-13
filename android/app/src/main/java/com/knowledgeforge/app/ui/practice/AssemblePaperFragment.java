package com.knowledgeforge.app.ui.practice;

import android.content.res.ColorStateList;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.GridLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;
import androidx.lifecycle.ViewModelProvider;

import com.google.android.material.card.MaterialCardView;
import com.google.android.material.chip.Chip;
import com.google.android.material.chip.ChipGroup;
import com.google.android.material.dialog.MaterialAlertDialogBuilder;
import com.google.android.material.switchmaterial.SwitchMaterial;
import com.knowledgeforge.app.R;
import com.knowledgeforge.app.data.repository.PracticeRepository;
import com.knowledgeforge.app.network.ApiClient;
import com.knowledgeforge.app.network.model.AssemblePaperResponse;
import com.knowledgeforge.app.network.model.KnowledgePoint;
import com.knowledgeforge.app.network.model.QuestionBank;
import com.knowledgeforge.app.network.model.SessionResponse;
import com.knowledgeforge.app.ui.common.Event;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** 组卷配置页。所有用户选择由 ViewModel 持有，Fragment 只负责渲染和转发点击。 */
public class AssemblePaperFragment extends Fragment {

    private static final String ARG_BANK_ID = "selected_bank_id";
    private static final int COLOR_PRIMARY = 0xFF6548F5;
    private static final int COLOR_TEXT = 0xFF191B3A;
    private static final int COLOR_SECONDARY = 0xFF777B9D;
    private static final int COLOR_SELECTED_BG = 0xFFF0EDFF;
    private static final int COLOR_BORDER = 0xFFE5E2FA;

    private TextView tvSelectedBankName;
    private TextView tvSelectedBankCount;
    private TextView tvKnowledgeClear;
    private TextView tvKnowledgeHint;
    private ChipGroup knowledgeChipGroup;
    private GridLayout questionTypeGrid;
    private ChipGroup difficultyChipGroup;
    private TextView tvQuestionCount;
    private TextView tvError;
    private TextView btnAssemble;
    private ProgressBar progressBar;
    private SwitchMaterial switchAllowPartial;

    private AssemblePaperViewModel viewModel;
    private boolean rendering;

    public AssemblePaperFragment() { }

    public static AssemblePaperFragment newInstance(int bankId) {
        AssemblePaperFragment fragment = new AssemblePaperFragment();
        Bundle args = new Bundle();
        args.putInt(ARG_BANK_ID, bankId);
        fragment.setArguments(args);
        return fragment;
    }

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater,
                             @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_assemble_paper, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View root, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(root, savedInstanceState);
        bindViews(root);
        initViewModel();
        observeViewModel();
        initListeners(root);
        int bankId = getArguments() == null ? -1 : getArguments().getInt(ARG_BANK_ID, -1);
        viewModel.loadBanks(bankId);
    }

    private void bindViews(View root) {
        tvSelectedBankName = root.findViewById(R.id.tvSelectedBankName);
        tvSelectedBankCount = root.findViewById(R.id.tvSelectedBankCount);
        tvKnowledgeClear = root.findViewById(R.id.tvKnowledgeClear);
        tvKnowledgeHint = root.findViewById(R.id.tvKnowledgeHint);
        knowledgeChipGroup = root.findViewById(R.id.knowledgeChipGroup);
        questionTypeGrid = root.findViewById(R.id.questionTypeGrid);
        difficultyChipGroup = root.findViewById(R.id.difficultyChipGroup);
        tvQuestionCount = root.findViewById(R.id.tvQuestionCount);
        tvError = root.findViewById(R.id.tvAssembleError);
        btnAssemble = root.findViewById(R.id.btnAssemblePaper);
        progressBar = root.findViewById(R.id.assembleProgress);
        switchAllowPartial = root.findViewById(R.id.switchAllowPartial);
    }

    private void initViewModel() {
        ApiClient apiClient = ApiClient.getInstance(requireContext());
        PracticeRepository repository = new PracticeRepository(
                apiClient.getPracticeApiService(), apiClient.getStatisticsApiService());
        AssemblePaperViewModelFactory factory = new AssemblePaperViewModelFactory(repository);
        viewModel = new ViewModelProvider(this, factory).get(AssemblePaperViewModel.class);
    }

    private void observeViewModel() {
        viewModel.getUiState().observe(getViewLifecycleOwner(), this::render);
        viewModel.getAssembleSuccess().observe(getViewLifecycleOwner(), event -> {
            if (event == null) return;
            AssemblePaperResponse result = event.getContentIfNotHandled();
            if (result != null) showAssembleSuccess(result);
        });
    }

    private void initListeners(View root) {
        root.findViewById(R.id.btnAssembleBack).setOnClickListener(v -> goBack());
        root.findViewById(R.id.btnAssembleHelp).setOnClickListener(v -> showHelp());
        root.findViewById(R.id.cardSelectedBank).setOnClickListener(v -> showBankChooser());
        root.findViewById(R.id.tvChooseAllBanks).setOnClickListener(v -> showBankChooser());
        tvKnowledgeClear.setOnClickListener(v -> viewModel.clearKnowledgePoints());
        root.findViewById(R.id.btnQuestionMinus).setOnClickListener(v -> {
            AssemblePaperUiState state = viewModel.getUiState().getValue();
            if (state != null) viewModel.setQuestionCount(state.getQuestionCount() - 1);
        });
        root.findViewById(R.id.btnQuestionPlus).setOnClickListener(v -> {
            AssemblePaperUiState state = viewModel.getUiState().getValue();
            if (state != null) viewModel.setQuestionCount(state.getQuestionCount() + 1);
        });
        switchAllowPartial.setOnCheckedChangeListener((buttonView, checked) -> {
            if (!rendering) viewModel.setAllowPartial(checked);
        });
        btnAssemble.setOnClickListener(v -> viewModel.assemble());
        tvError.setOnClickListener(v -> viewModel.retryLoadCurrentKnowledgePoints());
    }

    private void render(AssemblePaperUiState state) {
        if (state == null || getView() == null) return;
        rendering = true;
        progressBar.setVisibility(state.isBanksLoading() || state.isKnowledgeLoading()
                || state.isAssembling() ? View.VISIBLE : View.GONE);

        QuestionBank bank = state.getSelectedBank();
        if (bank == null) {
            tvSelectedBankName.setText(state.isBanksLoading() ? "正在加载开放题库…" : "请选择题库");
            tvSelectedBankCount.setText("仅显示管理员开放且有库存的题库");
        } else {
            tvSelectedBankName.setText(bank.getName() == null ? "未命名题库" : bank.getName());
            tvSelectedBankCount.setText("共 " + bank.getAvailableQuestionCount() + " 道可练习题 · 点击更换");
        }

        renderKnowledgePoints(state);
        renderQuestionTypes(state);
        renderDifficulty(state);
        tvQuestionCount.setText(String.valueOf(state.getQuestionCount()));
        switchAllowPartial.setChecked(state.isAllowPartial());

        if (state.getErrorMessage() == null || state.getErrorMessage().trim().isEmpty()) {
            tvError.setVisibility(View.GONE);
        } else {
            tvError.setText(state.getErrorMessage());
            tvError.setVisibility(View.VISIBLE);
        }

        boolean canAssemble = bank != null && bank.isCanAssemble() && !state.isAssembling();
        btnAssemble.setEnabled(canAssemble);
        View backButton = getView().findViewById(R.id.btnAssembleBack);
        if (backButton != null) backButton.setEnabled(!state.isAssembling());
        btnAssemble.setAlpha(canAssemble ? 1f : 0.58f);
        btnAssemble.setText(state.isAssembling()
                ? "正在生成试卷…" : "开始练习  ·  " + state.getQuestionCount() + " 题  →");
        rendering = false;
    }

    private void renderKnowledgePoints(AssemblePaperUiState state) {
        knowledgeChipGroup.removeAllViews();
        if (state.isKnowledgeLoading()) {
            tvKnowledgeHint.setText("正在加载知识点…");
        } else if (state.getKnowledgePoints().isEmpty()) {
            tvKnowledgeHint.setText("该题库暂无可筛选知识点；不选择时使用整个题库范围");
        } else {
            tvKnowledgeHint.setText(state.getSelectedKnowledgeIds().isEmpty()
                    ? "不选择知识点时，将从整个题库范围组卷"
                    : "已选择 " + state.getSelectedKnowledgeIds().size() + " 个知识点");
        }
        tvKnowledgeClear.setVisibility(state.getSelectedKnowledgeIds().isEmpty()
                ? View.INVISIBLE : View.VISIBLE);

        for (KnowledgePoint point : state.getKnowledgePoints()) {
            if (point == null) continue;
            Chip chip = createChip(point.getName() + "  " + point.getAvailableQuestionCount(),
                    state.getSelectedKnowledgeIds().contains(point.getKnowledgeId()), false);
            chip.setOnClickListener(v -> viewModel.toggleKnowledgePoint(point.getKnowledgeId()));
            knowledgeChipGroup.addView(chip);
        }
    }

    private void renderQuestionTypes(AssemblePaperUiState state) {
        questionTypeGrid.removeAllViews();
        QuestionBank bank = state.getSelectedBank();
        addQuestionTypeCard(state, bank, "SINGLE_CHOICE", "单选题", "✓", 0);
        addQuestionTypeCard(state, bank, "MULTIPLE_CHOICE", "多选题", "☷", 1);
        addQuestionTypeCard(state, bank, "TRUE_FALSE", "判断题", "✓", 2);
        addQuestionTypeCard(state, bank, "SHORT_ANSWER", "简答题", "✎", 3);
    }

    private void addQuestionTypeCard(AssemblePaperUiState state,
                                    QuestionBank bank,
                                    String type,
                                    String label,
                                    String symbol,
                                    int column) {
        int stock = getCount(bank == null ? null : bank.getQuestionTypeCounts(), type);
        boolean hasInventory = bank != null && (stock > 0
                || bank.getQuestionTypeCounts() == null || bank.getQuestionTypeCounts().isEmpty());
        boolean selected = state.getSelectedQuestionTypes().contains(type);

        MaterialCardView card = new MaterialCardView(requireContext());
        card.setRadius(dp(14));
        card.setCardElevation(0);
        card.setStrokeWidth(dp(selected ? 2 : 1));
        card.setStrokeColor(ColorStateList.valueOf(selected ? COLOR_PRIMARY : COLOR_BORDER));
        card.setCardBackgroundColor(selected ? COLOR_SELECTED_BG : 0xFFFFFFFF);
        card.setEnabled(hasInventory);
        card.setAlpha(hasInventory ? 1f : 0.42f);

        LinearLayout content = new LinearLayout(requireContext());
        content.setOrientation(LinearLayout.VERTICAL);
        content.setGravity(android.view.Gravity.CENTER);
        content.setPadding(dp(2), dp(9), dp(2), dp(8));

        TextView icon = new TextView(requireContext());
        icon.setText(symbol);
        icon.setTextSize(21);
        icon.setTextColor(selected ? COLOR_PRIMARY : COLOR_SECONDARY);
        icon.setGravity(android.view.Gravity.CENTER);
        content.addView(icon, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(28)));

        TextView title = new TextView(requireContext());
        title.setText(label);
        title.setTextSize(12);
        title.setTextColor(selected ? COLOR_PRIMARY : COLOR_TEXT);
        title.setGravity(android.view.Gravity.CENTER);
        title.setMaxLines(1);
        content.addView(title, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(22)));

        TextView count = new TextView(requireContext());
        count.setText(bank == null ? "-- 道"
                : (bank.getQuestionTypeCounts() == null || bank.getQuestionTypeCounts().isEmpty()
                ? "可选" : stock + " 道"));
        count.setTextSize(10);
        count.setTextColor(COLOR_SECONDARY);
        count.setGravity(android.view.Gravity.CENTER);
        content.addView(count, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(18)));

        card.addView(content);
        GridLayout.LayoutParams params = new GridLayout.LayoutParams(
                GridLayout.spec(0, 1f), GridLayout.spec(column, 1f));
        params.width = 0;
        params.height = dp(91);
        params.setMargins(dp(3), 0, dp(3), dp(3));
        questionTypeGrid.addView(card, params);
        if (hasInventory) card.setOnClickListener(v -> viewModel.toggleQuestionType(type));
    }

    private void renderDifficulty(AssemblePaperUiState state) {
        difficultyChipGroup.removeAllViews();
        QuestionBank bank = state.getSelectedBank();
        String[] keys = {"all", "easy", "normal", "hard"};
        String[] names = {"全部", "简单", "中等", "困难"};
        for (int i = 0; i < keys.length; i++) {
            String key = keys[i];
            String text = names[i];
            if (bank != null && !"all".equals(key)) {
                int count = getDifficultyCount(bank.getDifficultyCounts(), key);
                text += "  " + count;
            }
            Chip chip = createChip(text, key.equals(state.getDifficulty()), true);
            boolean available = "all".equals(key) || bank == null
                    || bank.getDifficultyCounts() == null || bank.getDifficultyCounts().isEmpty()
                    || getDifficultyCount(bank.getDifficultyCounts(), key) > 0;
            chip.setEnabled(available);
            chip.setAlpha(available ? 1f : 0.42f);
            chip.setOnClickListener(v -> {
                if (available) viewModel.setDifficulty(key);
            });
            difficultyChipGroup.addView(chip);
        }
    }

    private Chip createChip(String text, boolean checked, boolean choice) {
        Chip chip = new Chip(requireContext());
        chip.setText(text);
        chip.setTextSize(12);
        chip.setCheckable(true);
        chip.setClickable(true);
        chip.setChecked(checked);
        chip.setChipCornerRadius(dp(18));
        chip.setChipMinHeight(dp(34));
        chip.setChipBackgroundColor(ColorStateList.valueOf(checked ? COLOR_SELECTED_BG : 0xFFF1F0F8));
        chip.setChipStrokeColor(ColorStateList.valueOf(checked ? 0xFFB9A9FF : 0x00000000));
        chip.setChipStrokeWidth(dp(checked ? 1 : 0));
        chip.setTextColor(checked ? COLOR_PRIMARY : COLOR_TEXT);
        chip.setEnsureMinTouchTargetSize(false);
        return chip;
    }

    private void showBankChooser() {
        AssemblePaperUiState state = viewModel.getUiState().getValue();
        if (state == null || state.getBanks().isEmpty()) {
            Toast.makeText(requireContext(), "暂无开放题库", Toast.LENGTH_SHORT).show();
            return;
        }
        List<QuestionBank> banks = state.getBanks();
        String[] names = new String[banks.size()];
        for (int i = 0; i < banks.size(); i++) {
            QuestionBank bank = banks.get(i);
            names[i] = (bank.getName() == null ? "未命名题库" : bank.getName())
                    + "（" + bank.getAvailableQuestionCount() + " 题）"
                    + (bank.isCanAssemble() ? "" : " · 暂不可组卷");
        }
        new MaterialAlertDialogBuilder(requireContext())
                .setTitle("选择题库")
                .setItems(names, (dialog, which) -> {
                    QuestionBank bank = banks.get(which);
                    if (bank.isCanAssemble()) viewModel.selectBank(bank.getId());
                    else Toast.makeText(requireContext(),
                            bank.getUnavailableReason() == null ? "该题库暂无可练习题目" : bank.getUnavailableReason(),
                            Toast.LENGTH_SHORT).show();
                })
                .setNegativeButton("取消", null)
                .show();
    }

    private void showHelp() {
        new MaterialAlertDialogBuilder(requireContext())
                .setTitle("组卷规则说明")
                .setMessage("题型范围：从已选择的题型中随机抽题，题量在所选题型间均分。\n\n难度范围：选择「全部」时，题量在简单、中等、困难之间均分；选择单一难度时，全部题目使用该难度。\n\n知识点：可多选；不选择表示不限制知识点。\n\n库存不足：默认不允许少题生成；开启部分组卷后，后端会按符合条件的实际库存生成。")
                .setPositiveButton("明白了", null)
                .show();
    }

    private void showAssembleSuccess(AssemblePaperResponse result) {
        String title = result.getPaper().getTitle();
        if (title == null || title.trim().isEmpty()) title = "练习试卷";
        SessionResponse session = result.getSession();
        String message = title + "\n共生成 " + result.getPaper().getQuestionCount() + " 道题";
        if (session != null) {
            message += "\n练习会话 ID：" + session.getSessionId();
            message += "\n\n试卷和首次练习会话已创建成功。答题页面将在下一阶段接入。";
        } else {
            message += "\n\n试卷已生成，但响应中没有返回首次练习会话。";
        }
        new MaterialAlertDialogBuilder(requireContext())
                .setTitle("组卷成功")
                .setMessage(message)
                .setPositiveButton("返回练习页", (dialog, which) -> goBack())
                .setNegativeButton("留在此页", null)
                .show();
    }

    public boolean isAssembling() {
        AssemblePaperUiState state = viewModel == null ? null : viewModel.getUiState().getValue();
        return state != null && state.isAssembling();
    }

    private void goBack() {
        Fragment parent = getParentFragment();
        if (parent instanceof PracticeFragment) {
            ((PracticeFragment) parent).handleBackPressed();
        }
    }

    private int getCount(Map<String, Integer> map, String key) {
        if (map == null) return 0;
        Integer value = map.get(key);
        if (value == null) value = map.get(key.toLowerCase());
        return value == null ? 0 : Math.max(0, value);
    }

    private int getDifficultyCount(Map<String, Integer> map, String key) {
        return getCount(map, key);
    }

    private int dp(float value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
