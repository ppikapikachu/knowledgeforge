package com.knowledgeforge.app.network.model;

import java.util.ArrayList;
import java.util.List;

/** 练习入口页聚合数据；各接口独立失败时仍保留其他成功数据。 */
public class PracticeLandingData {
    private List<QuestionBank> questionBanks = new ArrayList<>();
    private List<SessionListItem> activeSessions = new ArrayList<>();
    private List<PaperListItem> papers = new ArrayList<>();
    private UserStatisticsResponse statistics;
    private final List<String> errors = new ArrayList<>();

    public List<QuestionBank> getQuestionBanks() { return questionBanks; }
    public void setQuestionBanks(List<QuestionBank> value) {
        questionBanks = value == null ? new ArrayList<>() : value;
    }

    public List<SessionListItem> getActiveSessions() { return activeSessions; }
    public void setActiveSessions(List<SessionListItem> value) {
        activeSessions = value == null ? new ArrayList<>() : value;
    }

    public List<PaperListItem> getPapers() { return papers; }
    public void setPapers(List<PaperListItem> value) {
        papers = value == null ? new ArrayList<>() : value;
    }

    public UserStatisticsResponse getStatistics() { return statistics; }
    public void setStatistics(UserStatisticsResponse value) { statistics = value; }

    public void addError(String message) {
        if (message != null && !message.trim().isEmpty()) errors.add(message);
    }

    public List<String> getErrors() { return errors; }
    public boolean hasErrors() { return !errors.isEmpty(); }
}
