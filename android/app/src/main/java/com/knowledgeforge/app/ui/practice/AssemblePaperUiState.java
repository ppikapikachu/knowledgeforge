package com.knowledgeforge.app.ui.practice;

import com.knowledgeforge.app.network.model.KnowledgePoint;
import com.knowledgeforge.app.network.model.QuestionBank;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/** 组卷配置页不可变 UI 状态快照。 */
public class AssemblePaperUiState {
    private final boolean banksLoading;
    private final boolean knowledgeLoading;
    private final boolean assembling;
    private final List<QuestionBank> banks;
    private final QuestionBank selectedBank;
    private final List<KnowledgePoint> knowledgePoints;
    private final Set<Integer> selectedKnowledgeIds;
    private final Set<String> selectedQuestionTypes;
    private final String difficulty;
    private final int questionCount;
    private final boolean allowPartial;
    private final String errorMessage;

    public AssemblePaperUiState(boolean banksLoading,
                                boolean knowledgeLoading,
                                boolean assembling,
                                List<QuestionBank> banks,
                                QuestionBank selectedBank,
                                List<KnowledgePoint> knowledgePoints,
                                Set<Integer> selectedKnowledgeIds,
                                Set<String> selectedQuestionTypes,
                                String difficulty,
                                int questionCount,
                                boolean allowPartial,
                                String errorMessage) {
        this.banksLoading = banksLoading;
        this.knowledgeLoading = knowledgeLoading;
        this.assembling = assembling;
        this.banks = banks == null ? new ArrayList<>() : new ArrayList<>(banks);
        this.selectedBank = selectedBank;
        this.knowledgePoints = knowledgePoints == null ? new ArrayList<>() : new ArrayList<>(knowledgePoints);
        this.selectedKnowledgeIds = selectedKnowledgeIds == null
                ? new LinkedHashSet<>() : new LinkedHashSet<>(selectedKnowledgeIds);
        this.selectedQuestionTypes = selectedQuestionTypes == null
                ? new LinkedHashSet<>() : new LinkedHashSet<>(selectedQuestionTypes);
        this.difficulty = difficulty;
        this.questionCount = questionCount;
        this.allowPartial = allowPartial;
        this.errorMessage = errorMessage;
    }

    public boolean isBanksLoading() { return banksLoading; }
    public boolean isKnowledgeLoading() { return knowledgeLoading; }
    public boolean isAssembling() { return assembling; }
    public List<QuestionBank> getBanks() { return banks; }
    public QuestionBank getSelectedBank() { return selectedBank; }
    public List<KnowledgePoint> getKnowledgePoints() { return knowledgePoints; }
    public Set<Integer> getSelectedKnowledgeIds() { return selectedKnowledgeIds; }
    public Set<String> getSelectedQuestionTypes() { return selectedQuestionTypes; }
    public String getDifficulty() { return difficulty; }
    public int getQuestionCount() { return questionCount; }
    public boolean isAllowPartial() { return allowPartial; }
    public String getErrorMessage() { return errorMessage; }
}
