package com.knowledgeforge.app.ui.navigation;

import com.knowledgeforge.app.MainActivity;

/** Navigation Component 中「我的」Tab 的根页面。 */
public class MineTabFragment extends ModuleTabFragment {

    public MineTabFragment() {
        super();
    }

    @Override
    protected int getTabId() {
        return MainActivity.TAB_MINE;
    }
}
