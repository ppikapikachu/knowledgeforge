package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

import java.util.List;

/**
 * 题库可练习知识点（对应后端 schema BankKnowledgePointsResponse，
 * 接口 GET /api/v1/practice/question-banks/{qb_id}/knowledge-points 的 data）。
 * 只返回存在已发布题目的知识点（真实 QuestionKnowledge 关联，禁止名称匹配），
 * 按可用题量倒序，供组卷前筛选 knowledge_ids。
 */
public class KnowledgePointsResponse {

    /** 题库 ID。 */
    @SerializedName("question_bank_id")
    private int questionBankId;

    /** 可练习知识点列表（按可用题量倒序）。 */
    @SerializedName("knowledge_points")
    private List<KnowledgePoint> knowledgePoints;

    public int getQuestionBankId() {
        return questionBankId;
    }

    public List<KnowledgePoint> getKnowledgePoints() {
        return knowledgePoints;
    }
}
