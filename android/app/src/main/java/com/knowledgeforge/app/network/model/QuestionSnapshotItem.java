package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

import java.util.List;

/**
 * 试卷题目面投影（对应后端 schema QuestionSnapshotItem，
 * 接口 GET /api/v1/practice/papers/{paper_id} 返回的 PaperDetailResponse.items[] 元素）。
 * 只含题干/选项/知识点/分值等题目面字段，不含标准答案与解析（白名单投影，天然安全）。
 */
public class QuestionSnapshotItem {

    /** 试卷题目项 ID（practice_paper_item 主键，答题时的 paper_item_id）。 */
    @SerializedName("paper_item_id")
    private int paperItemId;

    /** 题目在试卷中的序号（1 起）。 */
    @SerializedName("sort_order")
    private int sortOrder;

    /** 题型：SINGLE_CHOICE|MULTIPLE_CHOICE|TRUE_FALSE|SHORT_ANSWER。 */
    @SerializedName("question_type")
    private String questionType;

    /** 题目难度（1=简单 2=中等 3=困难）。 */
    @SerializedName("difficulty")
    private int difficulty;

    /** 难度名（easy|normal|hard）。 */
    @SerializedName("difficulty_name")
    private String difficultyName;

    /** 本题分值。 */
    @SerializedName("score")
    private double score;

    /** 题干内容。 */
    @SerializedName("content")
    private String content;

    /** 选项列表（仅选择题有值，判断/简答为空列表）。 */
    @SerializedName("options")
    private List<QuestionOptionInfo> options;

    /** 关联知识点列表（可为空）。 */
    @SerializedName("knowledge_points")
    private List<QuestionKnowledgePointInfo> knowledgePoints;

    public int getPaperItemId() {
        return paperItemId;
    }

    public int getSortOrder() {
        return sortOrder;
    }

    public String getQuestionType() {
        return questionType;
    }

    public int getDifficulty() {
        return difficulty;
    }

    public String getDifficultyName() {
        return difficultyName;
    }

    public double getScore() {
        return score;
    }

    public String getContent() {
        return content;
    }

    public List<QuestionOptionInfo> getOptions() {
        return options;
    }

    public List<QuestionKnowledgePointInfo> getKnowledgePoints() {
        return knowledgePoints;
    }
}
