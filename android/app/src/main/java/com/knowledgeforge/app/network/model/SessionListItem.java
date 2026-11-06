package com.knowledgeforge.app.network.model;

/**
 * 我的练习会话列表条目（对应后端 schema SessionListItem，
 * 接口 GET /api/v1/practice/sessions 分页信封的 items[] 元素）。
 * 字段与会话主记录 SessionResponse 完全一致，独立类便于日后扩展列表特有字段。
 */
public class SessionListItem extends SessionResponse {
}
