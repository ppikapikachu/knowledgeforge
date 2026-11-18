package com.knowledgeforge.app.ui.practice;

import com.knowledgeforge.app.network.model.KnowledgePoint;
import com.knowledgeforge.app.network.model.QuestionBank;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * 组卷配置页面的 UI 状态数据对象。
 *
 * <p>这个类不负责请求接口、不负责计算组卷参数，也不直接操作任何 Android View。
 * 它只负责把组卷页面当前需要展示的数据和状态集中保存起来，供
 * AssemblePaperViewModel 通过 LiveData 发布，再由 AssemblePaperFragment 观察并刷新界面。</p>
 *
 * <p>例如：题库是否正在加载、当前选中了哪个题库、勾选了哪些知识点、
 * 选择了哪些题型、题量是多少、是否正在请求后端组卷，以及当前需要展示的错误信息。</p>
 *
 * <p>集合字段在构造时会复制一份，避免调用方之后修改传入的原始 List/Set
 * 影响本对象。不过当前 getter 返回的是内部集合本身，因此这是“构造时复制”的状态对象，
 * 并非严格不可变对象。使用方应只读取集合，不要通过 getter 修改集合内容。</p>
 */
public class AssemblePaperUiState {

    // -------------------- 请求/页面过程状态 --------------------

    /**
     * 是否正在请求开放练习题库列表。
     *
     * <p>true：题库列表请求尚未完成，界面通常显示题库区域的加载状态；</p>
     * <p>false：题库加载完成，或者请求失败，界面根据 banks/errorMessage 显示内容。</p>
     */
    private final boolean banksLoading;

    /**
     * 是否正在请求当前题库的可练习知识点列表。
     *
     * <p>true：知识点区域显示加载状态；</p>
     * <p>false：知识点请求已结束，使用 knowledgePoints 展示数据，或使用 errorMessage 提示错误。</p>
     */
    private final boolean knowledgeLoading;

    /**
     * 是否正在向后端提交组卷请求。
     *
     * <p>true：正在调用组卷接口，界面应显示提交进度，并避免用户重复点击“生成试卷并开始”。</p>
     * <p>false：当前没有正在执行的组卷请求。</p>
     *
     * <p>这个字段也用于组卷期间的返回拦截：请求尚未完成时，不允许用户误操作离开组卷页面。</p>
     */
    private final boolean assembling;

    // -------------------- 服务端返回的数据 --------------------

    /**
     * 当前已加载的开放练习题库列表。
     *
     * <p>每个元素是一个 QuestionBank，通常包含题库 ID、名称、描述、可练习题量、
     * 各题型/难度库存以及是否允许组卷等信息。具体字段以 QuestionBank 模型为准。</p>
     *
     * <p>它用于题库选择弹窗/列表。用户选择某个题库后，selectedBank 会记录当前选中的题库。</p>
     */
    private final List<QuestionBank> banks;

    /**
     * 用户当前选择的题库。
     *
     * <p>组卷配置必须有一个明确的题库作为出题范围。选择题库后，页面会根据它的 ID
     * 请求该题库可练习的知识点，并根据它的库存数据限制题型、难度和题量。</p>
     *
     * <p>如果尚未选择题库，该字段可以为 null；具体是否允许 null 由 ViewModel 的初始化逻辑决定。</p>
     */
    private final QuestionBank selectedBank;

    /**
     * 当前选中题库下可用于练习筛选的知识点列表。
     *
     * <p>这些数据来自题库知识点接口。每个 KnowledgePoint 通常包含知识点 ID、名称、
     * 以及该知识点下可练习的题目数量。</p>
     *
     * <p>注意：knowledgePoints 表示“可以供用户选择的全部知识点”；
     * selectedKnowledgeIds 才表示“用户实际勾选的知识点 ID”。两者不要混淆。</p>
     */
    private final List<KnowledgePoint> knowledgePoints;

    // -------------------- 用户在组卷表单中的选择 --------------------

    /**
     * 用户当前勾选的知识点 ID 集合。
     *
     * <p>集合保存的是知识点 ID，而不是知识点对象或名称。提交组卷请求时，
     * 这些 ID 会组成请求体中的 knowledge_ids。</p>
     *
     * <p>空集合通常表示不限定具体知识点，即从当前题库符合其他筛选条件的题目中选题；
     * 最终含义仍以 ViewModel 组装请求参数的逻辑为准。</p>
     *
     * <p>使用 Set 是为了避免同一个知识点 ID 被重复选中。</p>
     */
    private final Set<Integer> selectedKnowledgeIds;

    /**
     * 用户当前选择的题型编码集合。
     *
     * <p>这是题型的标识集合，不是每种题型的数量。它用于表达用户希望本次练习包含哪些题型。</p>
     *
     * <p>题型数量由 ViewModel 根据 questionCount、选中的题型以及题型库存计算或分配，
     * 最终提交给后端的字段是 question_type_counts。</p>
     *
     * <p>Set<String> 中具体使用哪些字符串编码，应以 ViewModel 中添加/移除题型时使用的值，
     * 以及后端 API Schema 定义为准；不要在 UI 层自行拼写另一套编码。</p>
     */
    private final Set<String> selectedQuestionTypes;

    /**
     * 当前选择的难度条件。
     *
     * <p>这是一个 String，而不是难度列表。实际可用值及它表示“全部难度”还是某一档难度，
     * 需要结合 ViewModel 中对 difficulty 的赋值和组卷请求转换逻辑确认。</p>
     *
     * <p>后端组卷请求使用 difficulty_distribution（各难度的题目数量分布）。
     * 因此本字段表达的是 UI 当前的难度选择条件；它本身并不等同于最终提交的数量分布。</p>
     */
    private final String difficulty;

    /**
     * 用户当前设置的本次练习总题量。
     *
     * <p>例如 questionCount = 20，表示用户希望本次练习生成 20 道题。</p>
     *
     * <p>组卷时，该值通常对应请求体中的 total_count。题型数量分配合计、难度数量分配合计，
     * 都必须与它保持一致；库存是否足够还需要根据题库和知识点筛选条件进行校验。</p>
     */
    private final int questionCount;

    /**
     * 库存不足时是否允许后端按实际可用题目数量生成较少题目的试卷。
     *
     * <p>false：不允许部分组卷；如果符合条件的题目不足，后端应返回库存不足错误，客户端提示用户调整条件。</p>
     * <p>true：允许部分组卷；后端可以在符合条件的题目不足时，按实际可用数量生成试卷。</p>
     *
     * <p>该字段对应组卷接口请求体中的 allow_partial。它不是“是否允许题目数量不一致”的通用开关，
     * 只控制库存不足时能否部分生成。</p>
     */
    private final boolean allowPartial;

    /**
     * 当前页面需要向用户展示的错误信息。
     *
     * <p>例如题库加载失败、知识点加载失败、参数校验失败或组卷请求失败。</p>
     *
     * <p>null 或空字符串表示当前没有需要展示的错误；非空时由 Fragment 将文本显示在错误提示区域。</p>
     *
     * <p>这里保存的是用于 UI 展示的文本，不保存 Throwable、HTTP 响应对象或 ApiException。</p>
     */
    private final String errorMessage;

    /**
     * 创建一次组卷页面状态快照。
     *
     * <p>ViewModel 在页面状态变化时创建新的 AssemblePaperUiState，随后通过 LiveData 发布。
     * 例如题库加载开始时创建 banksLoading=true 的状态；加载结束后再创建包含题库数据的新状态。</p>
     *
     * @param banksLoading          是否正在加载开放题库列表
     * @param knowledgeLoading      是否正在加载当前题库的知识点列表
     * @param assembling            是否正在提交组卷请求
     * @param banks                 已加载的开放题库列表；传 null 时转换为空列表
     * @param selectedBank          当前选中的题库；可以为 null，表示尚未选定题库
     * @param knowledgePoints      当前题库可供选择的知识点列表；传 null 时转换为空列表
     * @param selectedKnowledgeIds 用户已勾选的知识点 ID；传 null 时转换为空集合
     * @param selectedQuestionTypes 用户已选择的题型编码；传 null 时转换为空集合
     * @param difficulty            当前难度选择值；具体编码含义由 ViewModel 的赋值逻辑决定
     * @param questionCount        用户希望生成的练习总题量
     * @param allowPartial         库存不足时是否允许部分组卷
     * @param errorMessage         当前需要展示的错误文本；null 表示没有错误
     */
    public AssemblePaperUiState(boolean banksLoading,
                                boolean knowledgeLoading,
                                boolean assembling,
                                List<QuestionBank> banks,
                                QuestionBank selectedBank,
                                List<KnowledgePoint> knowledgePoints,
                                Set<Integer> selectedKnowledgeIds,
                                Set<String> selectedQuestionTypes,
                                String difficulty,
                                int questionCount,
                                boolean allowPartial,
                                String errorMessage) {
        this.banksLoading = banksLoading;
        this.knowledgeLoading = knowledgeLoading;
        this.assembling = assembling;

        // 复制传入的列表，避免外部继续修改原列表时影响当前状态对象。
        // 如果传 null，则使用空列表，避免调用方每次读取时都要判空。
        this.banks = banks == null ? new ArrayList<>() : new ArrayList<>(banks);

        // 当前选择的题库对象；未选择时保留 null。
        this.selectedBank = selectedBank;

        // 复制知识点列表。它是可选项数据，不代表用户已经勾选这些知识点。
        this.knowledgePoints = knowledgePoints == null
                ? new ArrayList<>()
                : new ArrayList<>(knowledgePoints);

        // 复制已选知识点 ID，使用 LinkedHashSet 保留用户选择的插入顺序，同时去除重复 ID。
        this.selectedKnowledgeIds = selectedKnowledgeIds == null
                ? new LinkedHashSet<>()
                : new LinkedHashSet<>(selectedKnowledgeIds);

        // 复制已选题型编码，使用 LinkedHashSet 保留选择顺序并避免重复题型。
        this.selectedQuestionTypes = selectedQuestionTypes == null
                ? new LinkedHashSet<>()
                : new LinkedHashSet<>(selectedQuestionTypes);

        // 保存当前难度选择值；具体字符串含义应与 ViewModel/API 中的编码保持一致。
        this.difficulty = difficulty;

        // 保存用户设置的总题量。
        this.questionCount = questionCount;

        // 保存库存不足时是否允许部分组卷。
        this.allowPartial = allowPartial;

        // 保存当前页面要展示的错误信息；null 表示没有错误提示。
        this.errorMessage = errorMessage;
    }

    // -------------------- 以下 getter 供 ViewModel/Fragment 读取页面状态 --------------------

    /** @return 是否正在加载题库列表 */
    public boolean isBanksLoading() {
        return banksLoading;
    }

    /** @return 是否正在加载当前题库的知识点列表 */
    public boolean isKnowledgeLoading() {
        return knowledgeLoading;
    }

    /** @return 是否正在提交组卷请求 */
    public boolean isAssembling() {
        return assembling;
    }

    /** @return 已加载的开放练习题库列表；调用方应只读，不要直接修改返回的集合 */
    public List<QuestionBank> getBanks() {
        return banks;
    }

    /** @return 当前选中的题库；尚未选择时为 null */
    public QuestionBank getSelectedBank() {
        return selectedBank;
    }

    /** @return 当前题库下可供选择的知识点列表；调用方应只读 */
    public List<KnowledgePoint> getKnowledgePoints() {
        return knowledgePoints;
    }

    /** @return 用户已经勾选的知识点 ID 集合；调用方应只读 */
    public Set<Integer> getSelectedKnowledgeIds() {
        return selectedKnowledgeIds;
    }

    /** @return 用户已经选择的题型编码集合；调用方应只读 */
    public Set<String> getSelectedQuestionTypes() {
        return selectedQuestionTypes;
    }

    /** @return 当前选择的难度条件值；具体编码含义由 ViewModel 定义 */
    public String getDifficulty() {
        return difficulty;
    }

    /** @return 用户设置的本次练习总题量 */
    public int getQuestionCount() {
        return questionCount;
    }

    /** @return 库存不足时是否允许部分组卷 */
    public boolean isAllowPartial() {
        return allowPartial;
    }

    /** @return 当前需要显示的错误文本；null 或空字符串表示没有错误 */
    public String getErrorMessage() {
        return errorMessage;
    }
}
