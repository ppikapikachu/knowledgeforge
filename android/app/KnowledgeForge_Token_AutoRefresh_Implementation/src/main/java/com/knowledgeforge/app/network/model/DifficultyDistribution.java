package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;

/**
 * 难度分布（对应后端 schema app.schemas.practice.DifficultyDistribution）。
 * easy=难度 1（简单）、normal=难度 2（中等）、hard=难度 3（困难）各难度题量。
 * 用于组卷请求 AssemblePaperRequest.difficulty_distribution（三项之和须等于 total_count），
 * 也用于组卷参数快照 AssemblyConfigInfo.difficulty_distribution。
 */
public class DifficultyDistribution {

    /** 简单题数量（difficulty=1）。 */
    @SerializedName("easy")
    private int easy;

    /** 中等题数量（difficulty=2）。 */
    @SerializedName("normal")
    private int normal;

    /** 困难题数量（difficulty=3）。 */
    @SerializedName("hard")
    private int hard;

    public DifficultyDistribution() {
    }

    public DifficultyDistribution(int easy, int normal, int hard) {
        this.easy = easy;
        this.normal = normal;
        this.hard = hard;
    }

    public int getEasy() {
        return easy;
    }

    public void setEasy(int easy) {
        this.easy = easy;
    }

    public int getNormal() {
        return normal;
    }

    public void setNormal(int normal) {
        this.normal = normal;
    }

    public int getHard() {
        return hard;
    }

    public void setHard(int hard) {
        this.hard = hard;
    }
}
