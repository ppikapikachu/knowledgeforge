package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

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
