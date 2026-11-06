package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;
import java.util.List;

public class KnowledgePointsResponse {
    @SerializedName("knowledge_points")
    private List<KnowledgePoint> knowledgePoints;

    public List<KnowledgePoint> getKnowledgePoints() {
        return knowledgePoints;
    }
}
