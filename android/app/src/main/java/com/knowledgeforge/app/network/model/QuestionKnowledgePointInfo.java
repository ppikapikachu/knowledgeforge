package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 题目关联知识点（对应后端 schema QuestionKnowledgePointInfo，
 * 见于会话详情题目项 SessionDetailItem.knowledge_points）。
 */
public class QuestionKnowledgePointInfo {

    /** 知识点 ID。 */
    @SerializedName("knowledge_id")
    private int knowledgeId;

    /** 知识点名称。 */
    @SerializedName("name")
    private String name;

    /** 知识点难度（1=简单 2=中等 3=困难）。 */
    @SerializedName("difficulty")
    private int difficulty;

    /** 重要程度（如 core=核心 / important=重要 / normal=一般，以后端枚举为准）。 */
    @SerializedName("importance_level")
    private String importanceLevel;

    public int getKnowledgeId() {
        return knowledgeId;
    }

    public String getName() {
        return name;
    }

    public int getDifficulty() {
        return difficulty;
    }

    public String getImportanceLevel() {
        return importanceLevel;
    }
}
