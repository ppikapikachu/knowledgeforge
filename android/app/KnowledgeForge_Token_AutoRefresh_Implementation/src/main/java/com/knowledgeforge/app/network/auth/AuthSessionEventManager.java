package com.knowledgeforge.app.network.auth;

import java.util.Set;
import java.util.concurrent.CopyOnWriteArraySet;

/**
 * 全局登录状态事件管理器。
 *
 * 作用：
 * 1. 网络层发现登录状态彻底失效时，通知整个 App。
 * 2. MainActivity 负责监听事件并跳转登录页。
 * 3. 防止多个接口同时返回 40101 时重复跳转。
 *
 * 注意：
 * 该类不负责刷新 Token，也不直接操作 Activity。
 */
public final class AuthSessionEventManager {

    /**
     * 登录状态失效事件监听器。
     */
    public interface Listener {
        void onSessionExpired();
    }

    /**
     * 使用线程安全集合保存监听器。
     * MainActivity 在 onStart 注册，在 onStop 注销。
     */
    private static final Set<Listener> LISTENERS =
            new CopyOnWriteArraySet<>();

    /**
     * 保护登录状态和监听器注册过程。
     */
    private static final Object LOCK = new Object();

    /**
     * 当前登录状态是否已经失效。
     * 用于防止多个请求重复发送过期事件。
     */
    private static boolean expired = false;

    private AuthSessionEventManager() {
    }

    /**
     * 注册登录状态监听器。
     *
     * 如果注册时登录状态已经失效，
     * 立即通知新注册的监听器，避免丢失事件。
     */
    public static void addListener(Listener listener) {

        boolean shouldNotify;

        synchronized (LOCK) {
            LISTENERS.add(listener);
            shouldNotify = expired;
        }

        if (shouldNotify) {
            listener.onSessionExpired();
        }
    }

    /**
     * 注销监听器，避免 Activity 泄漏。
     */
    public static void removeListener(Listener listener) {
        LISTENERS.remove(listener);
    }

    /**
     * 通知 App 当前登录状态已经失效。
     *
     * 只允许通知一次，防止多个接口同时失败时
     * 重复启动 LoginActivity。
     */
    public static void notifySessionExpired() {

        synchronized (LOCK) {
            if (expired) {
                return;
            }

            expired = true;
        }

        for (Listener listener : LISTENERS) {
            listener.onSessionExpired();
        }
    }

    /**
     * 登录或注册成功后，重置登录状态。
     */
    public static void markAuthenticated() {

        synchronized (LOCK) {
            expired = false;
        }
    }
}