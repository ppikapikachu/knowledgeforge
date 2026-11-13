package com.knowledgeforge.app.ui.navigation;

import com.knowledgeforge.app.MainActivity;

/** Navigation Component 中「记录」Tab 的根页面。 */
public class RecordsTabFragment extends ModuleTabFragment {

    public RecordsTabFragment() {
        super();
    }

    @Override
    protected int getTabId() {
        return MainActivity.TAB_RECORDS;
    }
}
