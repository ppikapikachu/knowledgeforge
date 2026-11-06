package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

import java.util.List;

/**
 * 会话详情题目项（对应后端 schema SessionDetailItem，
 * 会话详情 SessionDetailResponse.items[] 元素，按试卷题序返回）。
 * 注意答案安全投影：未作答题不返回正确答案/我的答案/判分结果等字段（缺省为 null）。
 */
public class SessionDetailItem {

    /** 试卷题目项 ID（答题时的 paper_item_id）。 */
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

    /** 选项列表（仅选择题有值，其余题型为空列表）。 */
    @SerializedName("options")
    private List<QuestionOptionInfo> options;

    /** 关联知识点列表（可为空）。 */
    @SerializedName("knowledge_points")
    private List<QuestionKnowledgePointInfo> knowledgePoints;

    /** 标准答案（仅已提交题返回；单选如 "A"，多选如 "A,C"，判断如 "true"）。 */
    @SerializedName("correct_answer")
    private String correctAnswer;

    /** 答案解析（仅已提交题返回，可空）。 */
    @SerializedName("explanation")
    private String explanation;

    /**
     * 我的答案（仅已提交题返回，多态，按题型）：
     * 单选=选项键字符串、多选=选项键数组、判断=布尔、简答=文本。
     */
    @SerializedName("your_answer")
    private Object yourAnswer;

    /** 判分结果（仅已提交题返回：true=对 false=错 null=未判分）。 */
    @SerializedName("is_correct")
    private Boolean isCorrect;

    /** 判分状态（仅已提交题返回：graded|ungraded）。 */
    @SerializedName("grading_status")
    private String gradingStatus;

    /** 首次提交时间（ISO 8601 字符串，未提交为 null）。 */
    @SerializedName("first_submitted_at")
    private String firstSubmittedAt;

    /** 最近提交时间（ISO 8601 字符串，未提交为 null）。 */
    @SerializedName("last_submitted_at")
    private String lastSubmittedAt;

    /** 答题状态：unanswered|draft_saved|answered。 */
    @SerializedName("status")
    private String status;

    /** 是否已标记（收藏/标记题目，供稍后回看）。 */
    @SerializedName("is_marked")
    private boolean isMarked;

    /**
     * 本地草稿答案（多态，按题型同 your_answer 的形态；未保存草稿为 null）。
     * 注意：只有本接口返回草稿内容，其他接口不回显草稿值。
     */
    @SerializedName("draft_answer")
    private Object draftAnswer;

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

    public String getCorrectAnswer() {
        return correctAnswer;
    }

    public String getExplanation() {
        return explanation;
    }

    public Object getYourAnswer() {
        return yourAnswer;
    }

    public Boolean getIsCorrect() {
        return isCorrect;
    }

    public String getGradingStatus() {
        return gradingStatus;
    }

    public String getFirstSubmittedAt() {
        return firstSubmittedAt;
    }

    public String getLastSubmittedAt() {
        return lastSubmittedAt;
    }

    public String getStatus() {
        return status;
    }

    public boolean isMarked() {
        return isMarked;
    }

    public Object getDraftAnswer() {
        return draftAnswer;
    }
}
