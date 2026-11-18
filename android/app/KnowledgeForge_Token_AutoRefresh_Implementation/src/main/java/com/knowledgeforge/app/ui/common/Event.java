package com.knowledgeforge.app.ui.common;

// 我们把这种只应该消费一次的通知包装成 Event。
public class Event<T> {

    private final T content;

    private boolean handled = false;

    public Event(T content) {
        this.content = content;
    }

    public synchronized T getContentIfNotHandled() {

        if (handled) {
            return null;
        }

        handled = true;

        return content;
    }
}