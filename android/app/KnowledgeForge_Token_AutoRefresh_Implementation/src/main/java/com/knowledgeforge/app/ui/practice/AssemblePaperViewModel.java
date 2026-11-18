package com.knowledgeforge.app.ui.practice;

import androidx.lifecycle.LiveData;
import androidx.lifecycle.MutableLiveData;
import androidx.lifecycle.ViewModel;

import com.knowledgeforge.app.data.repository.PracticeRepository;
import com.knowledgeforge.app.network.callback.ApiCallback;
import com.knowledgeforge.app.network.model.AssemblePaperRequest;
import com.knowledgeforge.app.network.model.AssemblePaperResponse;
import com.knowledgeforge.app.network.model.DifficultyDistribution;
import com.knowledgeforge.app.ui.common.Event;
import com.knowledgeforge.app.network.model.KnowledgePoint;
import com.knowledgeforge.app.network.model.KnowledgePointsResponse;
import com.knowledgeforge.app.network.model.QuestionBank;
import com.knowledgeforge.app.network.model.ApiException;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * 组卷配置页 ViewModel。
 * UI 中只选择题型范围/难度范围；为匹配后端数量分布 Schema，客户端把总题量均分到所选题型，
 * 「全部难度」则在 easy/normal/hard 之间均分，保证两个分布之和都等于 total_count。
 */
public class AssemblePaperViewModel extends ViewModel {

    private static final List<String> TYPE_ORDER = Arrays.asList(
            "SINGLE_CHOICE", "MULTIPLE_CHOICE", "TRUE_FALSE", "SHORT_ANSWER");
    private static final int MAX_QUESTION_COUNT = 200;

    private final PracticeRepository repository;
    private final MutableLiveData<AssemblePaperUiState> uiState = new MutableLiveData<>();
    private final MutableLiveData<Event<AssemblePaperResponse>> assembleSuccess = new MutableLiveData<>();

    private boolean banksLoading;
    private boolean knowledgeLoading;
    private boolean assembling;
    private boolean allowPartial;
    private boolean banksLoaded;
    private List<QuestionBank> banks = new ArrayList<>();
    private QuestionBank selectedBank;
    private List<KnowledgePoint> knowledgePoints = new ArrayList<>();
    private final Set<Integer> selectedKnowledgeIds = new LinkedHashSet<>();
    private final Set<String> selectedQuestionTypes = new LinkedHashSet<>();
    private String difficulty = "all";
    private int questionCount = 50;
    private String errorMessage;
    private int knowledgeRequestVersion;
    /** 同一组卷配置在网络结果不确定时复用同一个幂等键，避免重复创建快照。 */
    private String pendingIdempotencyKey;

    public AssemblePaperViewModel(PracticeRepository repository) {
        this.repository = repository;
        publish();
    }

    public LiveData<AssemblePaperUiState> getUiState() { return uiState; }
    public LiveData<Event<AssemblePaperResponse>> getAssembleSuccess() { return assembleSuccess; }

    public void loadBanks(int preferredBankId) {
        if (banksLoaded || banksLoading) return;
        banksLoading = true;
        errorMessage = null;
        publish();

        repository.getQuestionBanks(new ApiCallback<com.knowledgeforge.app.network.model.PageResponse<QuestionBank>>() {
            @Override
            public void onSuccess(com.knowledgeforge.app.network.model.PageResponse<QuestionBank> result) {
                banksLoading = false;
                banksLoaded = true;
                banks = result == null || result.getItems() == null
                        ? new ArrayList<>() : new ArrayList<>(result.getItems());

                QuestionBank preferred = findBank(preferredBankId);
                if (preferred != null && preferred.isCanAssemble()) {
                    applySelectedBank(preferred);
                } else {
                    QuestionBank firstAvailable = null;
                    for (QuestionBank bank : banks) {
                        if (bank != null && bank.isCanAssemble()) {
                            firstAvailable = bank;
                            break;
                        }
                    }
                    if (firstAvailable != null) {
                        applySelectedBank(firstAvailable);
                    } else {
                        selectedBank = null;
                        errorMessage = banks.isEmpty()
                                ? "暂无开放题库，请稍后重试"
                                : "当前开放题库暂无可组卷题目";
                        publish();
                    }
                }
            }

            @Override
            public void onError(ApiException error) {
                banksLoading = false;
                errorMessage = safeMessage(error, "题库加载失败，请点击重试");
                publish();
            }
        });
    }

    public void retryLoadBanks() {
        banksLoaded = false;
        loadBanks(-1);
    }

    public void selectBank(int bankId) {
        QuestionBank bank = findBank(bankId);
        if (bank == null || !bank.isCanAssemble()) return;
        if (selectedBank != null && selectedBank.getId() == bankId) return;
        applySelectedBank(bank);
    }

    private void applySelectedBank(QuestionBank bank) {
        selectedBank = bank;
        pendingIdempotencyKey = null;
        selectedKnowledgeIds.clear();
        knowledgePoints = new ArrayList<>();
        selectedQuestionTypes.clear();
        chooseDefaultQuestionType(bank);
        int stock = Math.max(1, bank.getAvailableQuestionCount());
        questionCount = Math.min(50, Math.min(MAX_QUESTION_COUNT, stock));
        errorMessage = null;
        loadKnowledgePoints(bank.getId());
        publish();
    }

    private void chooseDefaultQuestionType(QuestionBank bank) {
        Map<String, Integer> counts = bank.getQuestionTypeCounts();
        for (String type : TYPE_ORDER) {
            if (getCount(counts, type) > 0) {
                selectedQuestionTypes.add(type);
                return;
            }
        }
        // 某些旧数据可能没有题型库存映射；此时默认单选，后端仍会进行最终校验。
        selectedQuestionTypes.add("SINGLE_CHOICE");
    }

    private void loadKnowledgePoints(int bankId) {
        knowledgeLoading = true;
        final int version = ++knowledgeRequestVersion;
        publish();
        repository.getKnowledgePoints(bankId, new ApiCallback<KnowledgePointsResponse>() {
            @Override
            public void onSuccess(KnowledgePointsResponse result) {
                if (version != knowledgeRequestVersion) return;
                knowledgeLoading = false;
                knowledgePoints = result == null || result.getKnowledgePoints() == null
                        ? new ArrayList<>() : new ArrayList<>(result.getKnowledgePoints());
                errorMessage = null;
                publish();
            }

            @Override
            public void onError(ApiException error) {
                if (version != knowledgeRequestVersion) return;
                knowledgeLoading = false;
                errorMessage = safeMessage(error, "知识点加载失败");
                publish();
            }
        });
    }

    public void retryLoadCurrentKnowledgePoints() {
        if (selectedBank != null && !knowledgeLoading) {
            errorMessage = null;
            loadKnowledgePoints(selectedBank.getId());
        } else if (selectedBank == null) {
            retryLoadBanks();
        }
    }

    public void toggleKnowledgePoint(int knowledgeId) {
        if (selectedKnowledgeIds.contains(knowledgeId)) selectedKnowledgeIds.remove(knowledgeId);
        else selectedKnowledgeIds.add(knowledgeId);
        pendingIdempotencyKey = null;
        errorMessage = null;
        publish();
    }

    public void clearKnowledgePoints() {
        selectedKnowledgeIds.clear();
        pendingIdempotencyKey = null;
        errorMessage = null;
        publish();
    }

    public void toggleQuestionType(String type) {
        if (!TYPE_ORDER.contains(type)) return;
        if (selectedBank != null
                && selectedBank.getQuestionTypeCounts() != null
                && !selectedBank.getQuestionTypeCounts().isEmpty()
                && getCount(selectedBank.getQuestionTypeCounts(), type) <= 0) return;
        if (selectedQuestionTypes.contains(type)) {
            if (selectedQuestionTypes.size() == 1) {
                errorMessage = "至少保留一种题型";
            } else {
                selectedQuestionTypes.remove(type);
                errorMessage = null;
            }
        } else {
            if (selectedQuestionTypes.size() >= questionCount) {
                errorMessage = "当前题量为 " + questionCount + " 道，至少需要与选择的题型数量一致";
                publish();
                return;
            }
            selectedQuestionTypes.add(type);
            errorMessage = null;
        }
        pendingIdempotencyKey = null;
        publish();
    }

    public void setDifficulty(String value) {
        if ("all".equals(value) || "easy".equals(value)
                || "normal".equals(value) || "hard".equals(value)) {
            if (!difficulty.equals(value)) pendingIdempotencyKey = null;
            difficulty = value;
            errorMessage = null;
            publish();
        }
    }

    public void setQuestionCount(int value) {
        int max = MAX_QUESTION_COUNT;
        if (!allowPartial && selectedBank != null && selectedBank.getAvailableQuestionCount() > 0) {
            max = Math.min(max, selectedBank.getAvailableQuestionCount());
        }
        int min = Math.max(1, selectedQuestionTypes.size());
        int next = Math.max(min, Math.min(max, value));
        if (questionCount != next) pendingIdempotencyKey = null;
        questionCount = next;
        errorMessage = null;
        publish();
    }

    public void setAllowPartial(boolean value) {
        if (allowPartial != value) pendingIdempotencyKey = null;
        allowPartial = value;
        errorMessage = null;
        publish();
    }

    public void assemble() {
        if (assembling) return;
        if (selectedBank == null || !selectedBank.isCanAssemble()) {
            errorMessage = "请选择一个有可练习题目的题库";
            publish();
            return;
        }
        if (selectedQuestionTypes.isEmpty()) {
            errorMessage = "请至少选择一种题型";
            publish();
            return;
        }
        if (!allowPartial && questionCount > selectedBank.getAvailableQuestionCount()) {
            errorMessage = "题量超过题库当前可练习库存，请减少题量或开启部分组卷";
            publish();
            return;
        }

        Map<String, Integer> typeCounts = distributeQuestionTypes(questionCount, selectedQuestionTypes);
        DifficultyDistribution difficultyDistribution = buildDifficultyDistribution(questionCount, difficulty);

        // 本地先用题库汇总库存做一次校验；知识点与题型/难度的交叉库存仍以服务端校验为准。
        if (!allowPartial && selectedBank.getQuestionTypeCounts() != null
                && !selectedBank.getQuestionTypeCounts().isEmpty()) {
            for (Map.Entry<String, Integer> entry : typeCounts.entrySet()) {
                int stock = getCount(selectedBank.getQuestionTypeCounts(), entry.getKey());
                if (entry.getValue() > stock) {
                    errorMessage = typeDisplayName(entry.getKey()) + "库存不足：配置需要 "
                            + entry.getValue() + " 道，当前可用 " + stock + " 道";
                    publish();
                    return;
                }
            }
        }
        if (!allowPartial && selectedBank.getDifficultyCounts() != null
                && !selectedBank.getDifficultyCounts().isEmpty()) {
            if (difficultyDistribution.getEasy() > getCount(selectedBank.getDifficultyCounts(), "easy")
                    || difficultyDistribution.getNormal() > getCount(selectedBank.getDifficultyCounts(), "normal")
                    || difficultyDistribution.getHard() > getCount(selectedBank.getDifficultyCounts(), "hard")) {
                errorMessage = "当前难度库存不足，请调整难度范围或开启部分组卷";
                publish();
                return;
            }
        }

        int typeTotal = sum(typeCounts);
        int difficultyTotal = difficultyDistribution.getEasy()
                + difficultyDistribution.getNormal() + difficultyDistribution.getHard();
        if (typeTotal != questionCount || difficultyTotal != questionCount) {
            errorMessage = "组卷配置数量不一致，请重新检查";
            publish();
            return;
        }

        AssemblePaperRequest request = new AssemblePaperRequest(selectedBank.getId(), questionCount);
        request.setTitle(null);
        request.setKnowledgeIds(selectedKnowledgeIds.isEmpty()
                ? null : new ArrayList<>(selectedKnowledgeIds));
        request.setQuestionTypeCounts(typeCounts);
        request.setDifficultyDistribution(difficultyDistribution);
        request.setAllowPartial(allowPartial);
        request.setSelectionStrategy("random");

        assembling = true;
        errorMessage = null;
        publish();
        // 网络结果不确定时，相同配置重试复用同一幂等键，避免重复创建试卷快照。
        if (pendingIdempotencyKey == null) {
            pendingIdempotencyKey = UUID.randomUUID().toString();
        }
        final String idempotencyKey = pendingIdempotencyKey;
        repository.assemblePaper(idempotencyKey, request, new ApiCallback<AssemblePaperResponse>() {
            @Override
            public void onSuccess(AssemblePaperResponse result) {
                assembling = false;
                if (result == null || result.getPaper() == null) {
                    errorMessage = "组卷接口返回内容不完整，请刷新后重试";
                    publish();
                    return;
                }
                pendingIdempotencyKey = null;
                publish();
                assembleSuccess.setValue(new Event<>(result));
            }

            @Override
            public void onError(ApiException error) {
                assembling = false;
                errorMessage = safeMessage(error, "组卷失败，请稍后重试");
                publish();
            }
        });
    }

    private QuestionBank findBank(int id) {
        if (id <= 0) return null;
        for (QuestionBank bank : banks) {
            if (bank != null && bank.getId() == id) return bank;
        }
        return null;
    }

    private Map<String, Integer> distributeQuestionTypes(int total, Set<String> selected) {
        List<String> ordered = new ArrayList<>();
        for (String type : TYPE_ORDER) if (selected.contains(type)) ordered.add(type);
        Map<String, Integer> result = new LinkedHashMap<>();
        int each = total / ordered.size();
        int remainder = total % ordered.size();
        for (int i = 0; i < ordered.size(); i++) {
            result.put(ordered.get(i), each + (i < remainder ? 1 : 0));
        }
        return result;
    }

    private DifficultyDistribution buildDifficultyDistribution(int total, String selectedDifficulty) {
        if ("easy".equals(selectedDifficulty)) return new DifficultyDistribution(total, 0, 0);
        if ("normal".equals(selectedDifficulty)) return new DifficultyDistribution(0, total, 0);
        if ("hard".equals(selectedDifficulty)) return new DifficultyDistribution(0, 0, total);
        int easy = total / 3 + (total % 3 > 0 ? 1 : 0);
        int normal = total / 3 + (total % 3 > 1 ? 1 : 0);
        int hard = total - easy - normal;
        return new DifficultyDistribution(easy, normal, hard);
    }

    private String typeDisplayName(String type) {
        if ("SINGLE_CHOICE".equals(type)) return "单选题";
        if ("MULTIPLE_CHOICE".equals(type)) return "多选题";
        if ("TRUE_FALSE".equals(type)) return "判断题";
        return "简答题";
    }

    private int getCount(Map<String, Integer> counts, String key) {
        if (counts == null) return 0;
        Integer value = counts.get(key);
        if (value == null) value = counts.get(key.toLowerCase());
        return value == null ? 0 : Math.max(0, value);
    }

    private int sum(Map<String, Integer> values) {
        int total = 0;
        for (Integer value : values.values()) if (value != null) total += value;
        return total;
    }

    private String safeMessage(ApiException error, String fallback) {
        if (error == null || error.getMessage() == null || error.getMessage().trim().isEmpty()) {
            return fallback;
        }
        return error.getMessage();
    }

    private void publish() {
        uiState.setValue(new AssemblePaperUiState(
                banksLoading, knowledgeLoading, assembling, banks, selectedBank,
                knowledgePoints, selectedKnowledgeIds, selectedQuestionTypes,
                difficulty, questionCount, allowPartial, errorMessage));
    }
}
