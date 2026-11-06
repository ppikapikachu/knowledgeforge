package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 试卷快照头（对应后端 schema PaperResponse，practice_paper 不可变快照）。
 * 作为组卷响应 AssemblePaperResponse.paper、会话详情 SessionDetailResponse.paper 的字段。
 * 试卷一旦生成题目内容不再变化（源题后续修改不影响快照）。
 */
public class PaperResponse {

    /** 试卷 ID（practice_paper 主键）。 */
    @SerializedName("paper_id")
    private int paperId;

    /** 试卷标题。 */
    @SerializedName("title")
    private String title;

    /** 试卷题量。 */
    @SerializedName("question_count")
    private int questionCount;

    /** 试卷总分。 */
    @SerializedName("total_score")
    private double totalScore;

    /** 试卷状态：ready=可练习，archived=已归档（不可再发起新会话）。 */
    @SerializedName("status")
    private String status;

    /** 来源题库 ID（可空）。 */
    @SerializedName("source_question_bank_id")
    private Integer sourceQuestionBankId;

    /** 组卷参数快照（题型/难度分布等）；历史/异常数据可能为 null。 */
    @SerializedName("assembly_config")
    private AssemblyConfigInfo assemblyConfig;

    /** 快照版本（当前固定 1）。 */
    @SerializedName("snapshot_version")
    private int snapshotVersion;

    /** 快照内容哈希（SHA-256）。 */
    @SerializedName("snapshot_hash")
    private String snapshotHash;

    /** 组卷时间（ISO 8601 字符串，可空）。 */
    @SerializedName("created_at")
    private String createdAt;

    /** 归档时间（ISO 8601 字符串；未归档为 null）。 */
    @SerializedName("archived_at")
    private String archivedAt;

    public int getPaperId() {
        return paperId;
    }

    public String getTitle() {
        return title;
    }

    public int getQuestionCount() {
        return questionCount;
    }

    public double getTotalScore() {
        return totalScore;
    }

    public String getStatus() {
        return status;
    }

    public Integer getSourceQuestionBankId() {
        return sourceQuestionBankId;
    }

    public AssemblyConfigInfo getAssemblyConfig() {
        return assemblyConfig;
    }

    public int getSnapshotVersion() {
        return snapshotVersion;
    }

    public String getSnapshotHash() {
        return snapshotHash;
    }

    public String getCreatedAt() {
        return createdAt;
    }

    public String getArchivedAt() {
        return archivedAt;
    }
}
