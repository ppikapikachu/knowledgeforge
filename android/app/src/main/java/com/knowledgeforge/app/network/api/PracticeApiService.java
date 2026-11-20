package com.knowledgeforge.app.network.api;

import com.knowledgeforge.app.network.model.ApiResponse;
import com.knowledgeforge.app.network.model.AssemblePaperRequest;
import com.knowledgeforge.app.network.model.AssemblePaperResponse;
import com.knowledgeforge.app.network.model.DraftSaveRequest;
import com.knowledgeforge.app.network.model.DraftSaveResponse;
import com.knowledgeforge.app.network.model.KnowledgePointsResponse;
import com.knowledgeforge.app.network.model.MarkItemResponse;
import com.knowledgeforge.app.network.model.MarkRequest;
import com.knowledgeforge.app.network.model.PageResponse;
import com.knowledgeforge.app.network.model.PaperDetailResponse;
import com.knowledgeforge.app.network.model.PaperListItem;
import com.knowledgeforge.app.network.model.PaperResponse;
import com.knowledgeforge.app.network.model.ProgressRequest;
import com.knowledgeforge.app.network.model.ProgressUpdateResponse;
import com.knowledgeforge.app.network.model.QuestionBank;
import com.knowledgeforge.app.network.model.SessionAnswersResponse;
import com.knowledgeforge.app.network.model.SessionDetailResponse;
import com.knowledgeforge.app.network.model.SessionListItem;
import com.knowledgeforge.app.network.model.SessionResponse;
import com.knowledgeforge.app.network.model.SessionResultResponse;
import com.knowledgeforge.app.network.model.SubmitAnswerRequest;
import com.knowledgeforge.app.network.model.SubmitAnswerResponse;

import retrofit2.Call;
import retrofit2.http.Body;
import retrofit2.http.GET;
import retrofit2.http.Header;
import retrofit2.http.PATCH;
import retrofit2.http.POST;
import retrofit2.http.PUT;
import retrofit2.http.Path;
import retrofit2.http.Query;

/**
 * 练习相关接口（后端 tag「练习」中 Android 需要的 10 个）：
 * 题库选择（2）+ 组卷（1）+ 会话练习（5：详情/恢复/提交/进度/完成）+ 历史列表（2）。
 * 本文件只声明 HTTP 接口，不含业务逻辑；响应统一为后端封套 ApiResponse。
 * 通用规则：
 * - 路径参数 qb_id / session_id / paper_item_id 均为正整数，仅本人资源可见
 *   （他人资源统一 40401，不泄露存在性）；
 * - 分页参数 page 从 1 开始，page_size 默认 20、取值 1~100，null 时不发送（用默认值）；
 * - 组卷/提交的幂等：组卷用可选请求头 Idempotency-Key，提交用请求体内的 idempotency_key；
 * - 会话状态流转 in_progress → completed|abandoned，非 in_progress 会话拒绝修改类操作（40001）。
 */
public interface PracticeApiService {

    /**
     * 开放练习题库列表（GET /api/v1/practice/question-banks）：
     * 分页列出普通用户可见的练习题库（仅 is_available_for_practice=true）；
     * 空库存题库也返回（can_assemble=false 并给出 unavailable_reason）。
     *
     * @param page     页码（可选，从 1 开始，缺省第 1 页）
     * @param pageSize 每页条数（可选，默认 20，取值 1~100）
     * @param keyword  题库名称模糊搜索（去空格后非空才生效；空串=不筛选）
     * @return 题库分页列表
     */
    @GET("api/v1/practice/question-banks")
    Call<ApiResponse<PageResponse<QuestionBank>>> getQuestionBanks(
            @Query("page") Integer page,
            @Query("page_size") Integer pageSize,
            @Query("keyword") String keyword);

    /**
     * 题库可练习知识点（GET /api/v1/practice/question-banks/{qb_id}/knowledge-points）：
     * 只返回存在已发布题目的知识点（按可用题量倒序），供组卷前筛选 knowledge_ids；
     * 题库未开放或不存在返回 40401。
     *
     * @param qbId 题库 ID（正整数）
     * @return 题库 ID + 知识点列表
     */
    @GET("api/v1/practice/question-banks/{qb_id}/knowledge-points")
    Call<ApiResponse<KnowledgePointsResponse>> getQuestionBankKnowledgePoints(
            @Path("qb_id") int qbId);

    /**
     * 组卷（POST /api/v1/practice/papers/assemble）：按题型/难度分布从题库抽已发布题目，
     * 生成不可变快照试卷并自动创建首个练习会话；校验失败或库存不足（allow_partial=false）
     * 时零落库。
     * 幂等：idempotencyKey 传非空值时（1~128 位 [A-Za-z0-9._:~-]，首字符字母数字），
     * 同 key 同参重复请求返回原卷原会话（data.idempotent=true），同 key 异参报 40001 幂等冲突；
     * 传 null 表示不使用幂等（每次调用新建试卷）。
     *
     * @param idempotencyKey 幂等键（可选请求头 Idempotency-Key，可为 null）
     * @param request        组卷参数（question_bank_id/total_count 必填，可限定知识点/题型/难度分布）
     * @return 试卷快照 + 首个练习会话 + 幂等标记
     */
    @POST("api/v1/practice/papers/assemble")
    Call<ApiResponse<AssemblePaperResponse>> assemblePaper(
            @Header("Idempotency-Key") String idempotencyKey,
            @Body AssemblePaperRequest request);

    /**
     * 我的试卷列表（GET /api/v1/practice/papers）：
     * 分页查看本人拥有的试卷快照（含最近一次练习会话摘要 recent_session，无会话为 null）；
     * 不触发组卷，只读幂等。
     *
     * @param page     页码（可选，从 1 开始）
     * @param pageSize 每页条数（可选，默认 20，取值 1~100）
     * @return 试卷分页列表（PaperListItem = 试卷快照头 + 最近会话摘要）
     */
    @GET("api/v1/practice/papers")
    Call<ApiResponse<PageResponse<PaperListItem>>> getPapers(
            @Query("page") Integer page,
            @Query("page_size") Integer pageSize);

    /**
     * 我的练习会话列表（GET /api/v1/practice/sessions）：
     * 分页查看本人练习会话，可按状态筛选。
     *
     * @param status   会话状态筛选（in_progress|completed|abandoned；null=全部；
     *                 其他取值报 40001）
     * @param page     页码（可选，从 1 开始）
     * @param pageSize 每页条数（可选，默认 20，取值 1~100）
     * @return 会话分页列表
     */
    @GET("api/v1/practice/sessions")
    Call<ApiResponse<PageResponse<SessionListItem>>> getSessions(
            @Query("status") String status,
            @Query("page") Integer page,
            @Query("page_size") Integer pageSize);

    /**
     * 练习会话详情（GET /api/v1/practice/sessions/{session_id}）：
     * 一次返回恢复练习所需的会话 + 试卷快照头 + 全部题目项 + 进度摘要。
     * 安全投影：in_progress/abandoned 会话中未提交题目不返回
     * correct_answer/explanation/is_correct（仅已提交题返回自身判分结果），
     * completed 会话全量回顾；只读幂等（顺带刷新 last_active_at）。
     *
     * @param sessionId 练习会话 ID（正整数）
     * @return 会话详情（含题目项、草稿、标记与判分结果投影）
     */
    @GET("api/v1/practice/sessions/{session_id}")
    Call<ApiResponse<SessionDetailResponse>> getSessionDetail(
            @Path("session_id") int sessionId);

    /**
     * 恢复练习会话（POST /api/v1/practice/sessions/{session_id}/resume）：
     * 恢复一个 in_progress 会话继续答题并刷新活跃时间；
     * completed/abandoned 会话拒绝恢复（40001）；幂等（重复调用不改变状态）。
     *
     * @param sessionId 练习会话 ID（正整数）
     * @return 会话主记录
     */
    @POST("api/v1/practice/sessions/{session_id}/resume")
    Call<ApiResponse<SessionResponse>> resumeSession(@Path("session_id") int sessionId);

    /**
     * 提交答题并判分（POST /api/v1/practice/sessions/{session_id}/items/{paper_item_id}/submit）：
     * 按试卷快照内标准答案判分（源题后续变化不影响结果），追加答题记录并更新会话统计；
     * completed/abandoned 会话拒绝提交（40001）。
     * 幂等以请求体 idempotency_key 为准（必填 8~64 位）：同 key 同内容重复提交返回原记录
     * （data.idempotent=true），同 key 不同内容报 40001 幂等冲突，新 key 视为新一次尝试。
     *
     * @param sessionId   练习会话 ID（正整数）
     * @param paperItemId 试卷题目项 ID（须属于该会话的试卷）
     * @param request     答案（按题型多态）+ 幂等键 + 可选作答耗时
     * @return 答题记录 ID、判分结果、标准答案/解析（仅提交后返回）与会话进度
     */
    @POST("api/v1/practice/sessions/{session_id}/items/{paper_item_id}/submit")
    Call<ApiResponse<SubmitAnswerResponse>> submitAnswer(
            @Path("session_id") int sessionId,
            @Path("paper_item_id") int paperItemId,
            @Body SubmitAnswerRequest request);

    /**
     * 更新练习进度（PATCH /api/v1/practice/sessions/{session_id}/progress）：
     * 记录用户当前做到第几题（便于恢复练习位置），不改变答题状态与统计；
     * completed/abandoned 会话拒绝修改（40001）；幂等覆盖，current_item_order
     * 越界（不在 1..total_count）报 40001。
     *
     * @param sessionId 练习会话 ID（正整数）
     * @param request   当前题序（current_item_order 必填）
     * @return 会话 ID + 更新后的当前题序
     */
    @PATCH("api/v1/practice/sessions/{session_id}/progress")
    Call<ApiResponse<ProgressUpdateResponse>> updateProgress(
            @Path("session_id") int sessionId,
            @Body ProgressRequest request);

    /**
     * 完成练习会话（POST /api/v1/practice/sessions/{session_id}/complete）：
     * 会话标记为 completed 进入只读回顾；未答题目保留 unanswered，不伪造作答；
     * completed_at 只在首次完成时设置；幂等（已完成重复调用直接返回，不重复写完成时间）。
     *
     * @param sessionId 练习会话 ID（正整数）
     * @return 会话主记录（含重算后的统计）
     */
    @POST("api/v1/practice/sessions/{session_id}/complete")
    Call<ApiResponse<SessionResponse>> completeSession(@Path("session_id") int sessionId);

    // ==================== 以下为练习模块补充接口（2026-11 新增，不改已有方法） ====================

    /**
     * 开放题库详情（GET /api/v1/practice/question-banks/{qb_id}）：
     * 返回题库基本信息 + 可练习题量/题型分布/难度分布/可否组卷及原因；
     * 题库未开放或不存在统一 40401（不泄露存在性）；只读幂等。
     * 说明：is_available_for_practice 文档说明恒 true，当前后端实现响应体未包含该字段，
     * QuestionBank.isAvailableForPractice 反序列化结果可能为 null。
     *
     * @param qbId 题库 ID（正整数）
     * @return 题库详情（字段同列表项：可用题量/分布/可组卷性）
     */
    @GET("api/v1/practice/question-banks/{qb_id}")
    Call<ApiResponse<QuestionBank>> getQuestionBankDetail(@Path("qb_id") int qbId);

    /**
     * 试卷详情（GET /api/v1/practice/papers/{paper_id}）：
     * 返回试卷快照头 + 题目面投影 items[]（题干/选项/知识点/分值，
     * 不含正确答案与解析，白名单投影天然安全）；他人试卷 40401；只读幂等。
     *
     * @param paperId 试卷 ID（正整数）
     * @return 试卷详情（PaperResponse + 题目面投影列表）
     */
    @GET("api/v1/practice/papers/{paper_id}")
    Call<ApiResponse<PaperDetailResponse>> getPaperDetail(@Path("paper_id") int paperId);

    /**
     * 对试卷再练（POST /api/v1/practice/papers/{paper_id}/sessions）：
     * 基于既有不可变试卷快照新建练习会话（不重新组卷、不改题目），
     * 用于同一份试卷多轮练习；已归档试卷拒绝（40001）；非幂等（每次调用新建会话）。
     *
     * @param paperId 试卷 ID（正整数）
     * @return 新建的练习会话
     */
    @POST("api/v1/practice/papers/{paper_id}/sessions")
    Call<ApiResponse<SessionResponse>> createPaperSession(@Path("paper_id") int paperId);

    /**
     * 归档试卷（PATCH /api/v1/practice/papers/{paper_id}/archive）：
     * 软归档（status→archived）：归档后不可再发起新练习会话，
     * 历史试卷与会话仍可查看；幂等（重复归档直接返回）。
     *
     * @param paperId 试卷 ID（正整数）
     * @return 归档后的试卷快照头
     */
    @PATCH("api/v1/practice/papers/{paper_id}/archive")
    Call<ApiResponse<PaperResponse>> archivePaper(@Path("paper_id") int paperId);

    /**
     * 放弃练习会话（POST /api/v1/practice/sessions/{session_id}/abandon）：
     * 软结束会话（status→abandoned），不删除已提交答题与草稿数据，
     * 之后不可 resume/提交（40001）；幂等（重复调用直接返回）。
     *
     * @param sessionId 练习会话 ID（正整数）
     * @return 会话主记录（终态 abandoned）
     */
    @POST("api/v1/practice/sessions/{session_id}/abandon")
    Call<ApiResponse<SessionResponse>> abandonSession(@Path("session_id") int sessionId);

    /**
     * 整卷结果与解析（GET /api/v1/practice/sessions/{session_id}/result）：
     * 一次返回会话 + 全部题目结果投影（含我的作答/判分结果）+ 结果汇总（得分等）；
     * 答案安全投影同会话详情：in_progress/abandoned 会话未提交题目不返回
     * correct_answer/explanation/is_correct，completed 会话全量回顾；只读幂等。
     *
     * @param sessionId 练习会话 ID（正整数）
     * @return 整卷结果（会话 + 题目结果列表 + 汇总）
     */
    @GET("api/v1/practice/sessions/{session_id}/result")
    Call<ApiResponse<SessionResultResponse>> getSessionResult(@Path("session_id") int sessionId);

    /**
     * 会话答题记录（GET /api/v1/practice/sessions/{session_id}/answers）：
     * 每次提交追加一条记录（同 idempotency_key 重复提交不追加），
     * 按提交时间正序（created_at 正序、id 升序）返回；只读幂等。
     *
     * @param sessionId 练习会话 ID（正整数）
     * @return 会话 ID + 答题记录列表
     */
    @GET("api/v1/practice/sessions/{session_id}/answers")
    Call<ApiResponse<SessionAnswersResponse>> getSessionAnswers(@Path("session_id") int sessionId);

    /**
     * 保存题目草稿（PUT /api/v1/practice/sessions/{session_id}/items/{paper_item_id}/draft）：
     * 仅写草稿不判分、不进统计；同一题目项反复保存幂等覆盖，仅保留最新草稿；
     * answer 传 null 表示清空草稿；已答题项保存草稿后 status 保持 answered 不回退；
     * completed/abandoned 会话拒绝（40001）。
     *
     * @param sessionId   练习会话 ID（正整数）
     * @param paperItemId 试卷题目项 ID（须属于该会话的试卷）
     * @param request     草稿内容（answer 按题型多态，可为 null 清空）
     * @return 题目项状态 + 最新草稿内容
     */
    @PUT("api/v1/practice/sessions/{session_id}/items/{paper_item_id}/draft")
    Call<ApiResponse<DraftSaveResponse>> saveDraft(
            @Path("session_id") int sessionId,
            @Path("paper_item_id") int paperItemId,
            @Body DraftSaveRequest request);

    /**
     * 标记/取消标记题目（PATCH /api/v1/practice/sessions/{session_id}/items/{paper_item_id}/mark）：
     * 标记状态与作答状态相互独立，幂等（重复置同一值不报错）；
     * completed/abandoned 会话拒绝（40001）。
     *
     * @param sessionId   练习会话 ID（正整数）
     * @param paperItemId 试卷题目项 ID（须属于该会话的试卷）
     * @param request     标记状态（is_marked 必填）
     * @return 题目项 ID + 当前标记状态
     */
    @PATCH("api/v1/practice/sessions/{session_id}/items/{paper_item_id}/mark")
    Call<ApiResponse<MarkItemResponse>> markItem(
            @Path("session_id") int sessionId,
            @Path("paper_item_id") int paperItemId,
            @Body MarkRequest request);
}
