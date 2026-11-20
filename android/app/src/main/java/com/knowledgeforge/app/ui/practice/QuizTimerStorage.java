package com.knowledgeforge.app.ui.practice;

import android.content.Context;
import android.content.SharedPreferences;

/**
 * 刷题计时的本地持久化工具。
 *
 * <p>后端 SessionResponse.duration_ms 是完成会话时计算的累计耗时，并不提供
 * 每次进入页面时可以直接恢复的实时计时值。因此客户端按 session_id 保存计时，
 * 避免页面重建、切到后台或进程被系统回收后计时直接归零。</p>
 *
 * <p>只保存毫秒数，不保存 Activity、View 或运行中的 Handler。</p>
 */
public class QuizTimerStorage {

    /** 本工具专用的 SharedPreferences 文件名。 */
    private static final String PREF_NAME = "knowledgeforge_quiz_timer";

    /** SharedPreferences 实例，使用 Application Context 避免持有 Activity。 */
    private final SharedPreferences preferences;

    /**
     * 创建计时存储。
     *
     * @param context 任意 Context；内部会转换成 Application Context
     */
    public QuizTimerStorage(Context context) {
        preferences = context.getApplicationContext()
                .getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE);
    }

    /**
     * 读取指定会话已累计的练习时长。
     *
     * @param sessionId 练习会话 ID
     * @return 已累计毫秒数；首次进入时为 0
     */
    public long getElapsedMillis(int sessionId) {
        return preferences.getLong(buildKey(sessionId), 0L);
    }

    /**
     * 保存指定会话当前累计时长。
     * 使用 apply()，避免磁盘写入阻塞主线程。
     *
     * @param sessionId     练习会话 ID
     * @param elapsedMillis 当前累计毫秒数
     */
    public void saveElapsedMillis(int sessionId, long elapsedMillis) {
        preferences.edit()
                .putLong(buildKey(sessionId), Math.max(0L, elapsedMillis))
                .apply();
    }

    /**
     * 完成练习后清除计时缓存，避免下一轮同一张试卷的练习沿用旧时间。
     *
     * @param sessionId 已完成的会话 ID
     */
    public void clear(int sessionId) {
        preferences.edit().remove(buildKey(sessionId)).apply();
    }

    /** 为每个练习会话生成独立的 SharedPreferences key。 */
    private String buildKey(int sessionId) {
        return "session_elapsed_" + sessionId;
    }
}
