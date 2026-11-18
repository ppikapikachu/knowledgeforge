package com.knowledgeforge.app.network.model;

import com.google.gson.annotations.SerializedName;
import java.util.List;

/**
 * 分页信封（对应后端 schemas.common.PaginatedData 的通用分页结构）。
 * 后端所有分页列表接口的 data 均为该形状：items=当前页数据，
 * page=页码（从 1 开始）、page_size=每页条数（默认 20，取值 1~100）、total=总条数。
 */
public class PageResponse<T> {
    @SerializedName("items")
    private List<T> items;

    @SerializedName("page")
    private int page;

    @SerializedName("page_size")
    private int pageSize;

    @SerializedName("total")
    private int total;

    public List<T> getItems() { return items; }
    public int getPage() { return page; }
    public int getPageSize() { return pageSize; }
    public int getTotal() { return total; }
}
