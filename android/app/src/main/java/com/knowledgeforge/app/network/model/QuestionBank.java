package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;
import java.util.Map;

public class QuestionBank {
    @SerializedName("id")
    private int id;
    @SerializedName("name")
    private String name;
    @SerializedName("description")
    private String description;
    @SerializedName("available_question_count")
    private int availableQuestionCount;
    @SerializedName("question_type_counts")
    private Map<String, Integer> questionTypeCounts;
    @SerializedName("difficulty_counts")
    private Map<String, Integer> difficultyCounts;
    @SerializedName("can_assemble")
    private boolean canAssemble;
    @SerializedName("unavailable_reason")
    private String unavailableReason;

    public int getId() { return id; }
    public String getName() { return name; }
    public String getDescription() { return description; }
    public int getAvailableQuestionCount() { return availableQuestionCount; }
    public Map<String, Integer> getQuestionTypeCounts() { return questionTypeCounts; }
    public Map<String, Integer> getDifficultyCounts() { return difficultyCounts; }
    public boolean canAssemble() { return canAssemble; }
    public String getUnavailableReason() { return unavailableReason; }
}
