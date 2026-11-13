package com.knowledgeforge.app.ui.navigation;

import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;

import com.google.android.material.card.MaterialCardView;
import com.knowledgeforge.app.MainActivity;
import com.knowledgeforge.app.R;

/**
 * 练习、记录、我的三个根 Tab 的模块入口页。
 * 具体列表/详情页按业务开发逐步替换卡片点击回调，不影响底部导航结构。
 */
public class ModuleTabFragment extends Fragment {

    private static final String ARG_TAB_ID = "tab_id";

    public static ModuleTabFragment newInstance(int tabId) {
        ModuleTabFragment fragment = new ModuleTabFragment();
        Bundle args = new Bundle();
        args.putInt(ARG_TAB_ID, tabId);
        fragment.setArguments(args);
        return fragment;
    }

    public ModuleTabFragment() {
    }

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater,
                             @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {
        View root = inflater.inflate(R.layout.fragment_module_tab, container, false);

        int tabId = getTabId();

        TextView title = root.findViewById(R.id.tvModuleTitle);
        TextView subtitle = root.findViewById(R.id.tvModuleSubtitle);
        LinearLayout list = root.findViewById(R.id.moduleCardList);

        ModuleContent content = contentFor(tabId);
        title.setText(content.title);
        subtitle.setText(content.subtitle);

        for (ModuleItem module : content.items) {
            MaterialCardView card = (MaterialCardView) inflater.inflate(
                    R.layout.item_module_entry, list, false);
            ((TextView) card.findViewById(R.id.tvModuleEntryTitle)).setText(module.title);
            ((TextView) card.findViewById(R.id.tvModuleEntryDesc)).setText(module.description);
            list.addView(card);

            card.setOnClickListener(v -> Toast.makeText(
                    requireContext(),
                    "该业务页面将在对应模块开发时接入",
                    Toast.LENGTH_SHORT
            ).show());
        }

        return root;
    }


    /** 子类可固定返回各自 Tab ID，供 Navigation Component 直接实例化。 */
    protected int getTabId() {
        return getArguments() == null
                ? MainActivity.TAB_PRACTICE
                : getArguments().getInt(ARG_TAB_ID, MainActivity.TAB_PRACTICE);
    }

    private ModuleContent contentFor(int tabId) {
        if (tabId == MainActivity.TAB_PRACTICE) {
            return new ModuleContent(
                    "练习",
                    "选择题库与知识范围，生成属于你的练习卷",
                    new ModuleItem[]{
                            new ModuleItem("开放题库", "浏览管理员开放的题库与可练习题量"),
                            new ModuleItem("知识点范围", "按所选题库筛选可练习知识点"),
                            new ModuleItem("自定义组卷", "设置题量、题型与难度分布"),
                            new ModuleItem("练习答题", "保存草稿、标记待回看、提交并判分；题目评论放在题目详情内")
                    }
            );
        }

        if (tabId == MainActivity.TAB_RECORDS) {
            return new ModuleContent(
                    "练习记录",
                    "继续未完成的练习，或回顾已经完成的试卷",
                    new ModuleItem[]{
                            new ModuleItem("继续中的练习", "恢复 in_progress 会话与上次答题进度"),
                            new ModuleItem("我的试卷", "查看试卷快照、归档试卷或再次练习"),
                            new ModuleItem("练习会话", "查看进行中、已完成和已放弃的会话"),
                            new ModuleItem("答题历史", "按题目或练习会话查看提交记录"),
                            new ModuleItem("练习结果", "查看得分、答题结果、正确答案与解析")
                    }
            );
        }

        return new ModuleContent(
                "我的",
                "管理个人资料，查看自己的练习与答题统计",
                new ModuleItem[]{
                        new ModuleItem("个人资料", "查看或修改昵称、头像"),
                        new ModuleItem("学习统计", "练习次数、完成次数、累计用时与答题正确率"),
                        new ModuleItem("账号与安全", "管理当前登录状态与退出登录")
                }
        );
    }

    private static class ModuleContent {
        final String title;
        final String subtitle;
        final ModuleItem[] items;

        ModuleContent(String title, String subtitle, ModuleItem[] items) {
            this.title = title;
            this.subtitle = subtitle;
            this.items = items;
        }
    }

    private static class ModuleItem {
        final String title;
        final String description;

        ModuleItem(String title, String description) {
            this.title = title;
            this.description = description;
        }
    }
}
