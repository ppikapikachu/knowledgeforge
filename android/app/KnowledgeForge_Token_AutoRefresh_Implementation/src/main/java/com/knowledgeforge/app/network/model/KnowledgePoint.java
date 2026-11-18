package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 题库可练习知识点条目（对应后端 schema BankKnowledgePointItem，
 * 见于 KnowledgePointsResponse.knowledge_points）。
 * 只包含存在已发布题目的知识点（真实 QuestionKnowledge 关联），按可用题量倒序。
 */
public class KnowledgePoint {
    @SerializedName("knowledge_id")
    private int knowledgeId;
    @SerializedName("name")
    private String name;
    @SerializedName("available_question_count")
    private int availableQuestionCount;

    public int getKnowledgeId() { return knowledgeId; }
    public String getName() { return name; }
    public int getAvailableQuestionCount() { return availableQuestionCount; }
}
