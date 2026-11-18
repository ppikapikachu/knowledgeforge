package com.knowledgeforge.app.network.model;

import com.knowledgeforge.app.network.model.PaperListItem;
import com.knowledgeforge.app.network.model.QuestionBank;
import com.knowledgeforge.app.network.model.SessionListItem;
import com.knowledgeforge.app.network.model.UserInfo;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * 首页聚合数据。每个字段均来自后端现有接口；某个接口失败时保留其他成功数据。
 */
public class HomeDashboardData {

    private UserInfo user;
    private List<QuestionBank> questionBanks = Collections.emptyList();
    private List<SessionListItem> activeSessions = Collections.emptyList();
    private List<PaperListItem> recentPapers = Collections.emptyList();
    private final List<String> errors = new ArrayList<>();

    public UserInfo getUser() {
        return user;
    }

    public void setUser(UserInfo user) {
        this.user = user;
    }

    public List<QuestionBank> getQuestionBanks() {
        return questionBanks;
    }

    public void setQuestionBanks(List<QuestionBank> questionBanks) {
        this.questionBanks = questionBanks == null ? Collections.emptyList() : questionBanks;
    }

    public List<SessionListItem> getActiveSessions() {
        return activeSessions;
    }

    public void setActiveSessions(List<SessionListItem> activeSessions) {
        this.activeSessions = activeSessions == null ? Collections.emptyList() : activeSessions;
    }

    public List<PaperListItem> getRecentPapers() {
        return recentPapers;
    }

    public void setRecentPapers(List<PaperListItem> recentPapers) {
        this.recentPapers = recentPapers == null ? Collections.emptyList() : recentPapers;
    }

    public synchronized void addError(String message) {
        if (message != null && !message.trim().isEmpty()) {
            errors.add(message);
        }
    }

    public synchronized List<String> getErrors() {
        return new ArrayList<>(errors);
    }

    public synchronized boolean hasErrors() {
        return !errors.isEmpty();
    }
}
