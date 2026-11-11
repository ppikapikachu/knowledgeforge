package com.knowledgeforge.app;

import android.graphics.Color;
import android.os.Bundle;
import android.view.View;
import android.widget.Toast;

import androidx.activity.OnBackPressedCallback;
import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.fragment.app.Fragment;
import androidx.fragment.app.FragmentManager;
import androidx.fragment.app.FragmentTransaction;

import com.google.android.material.bottomnavigation.BottomNavigationView;
import com.knowledgeforge.app.ui.home.HomeFragment;
import com.knowledgeforge.app.ui.navigation.ModuleTabFragment;

/**
 * KnowledgeForge 主容器。
 *
 * 导航策略：
 * 1. 四个底部 Tab 对应四个根 Fragment；
 * 2. 使用 show/hide，不使用 replace，切换 Tab 时保留滚动位置和页面状态；
 * 3. 用固定 Tag 查找 Fragment，避免重复创建；
 * 4. 不把 Tab 根页面加入 back stack；
 * 5. 返回键在非首页 Tab 时先回首页，在首页才退出 Activity。
 */
public class MainActivity extends AppCompatActivity {

    public static final int TAB_HOME = R.id.nav_home;
    public static final int TAB_PRACTICE = R.id.nav_practice;
    public static final int TAB_RECORDS = R.id.nav_records;
    public static final int TAB_MINE = R.id.nav_mine;

    private static final String STATE_SELECTED_TAB = "selected_bottom_tab";

    private BottomNavigationView bottomNavigation;
    private Fragment currentFragment;
    private int selectedTabId = TAB_HOME;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        // 让状态栏与页面浅色背景融合，图标使用深色。
        getWindow().setStatusBarColor(Color.rgb(246, 245, 255));
        getWindow().getDecorView().setSystemUiVisibility(
                getWindow().getDecorView().getSystemUiVisibility()
                        | View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
        );

        bottomNavigation = findViewById(R.id.bottomNavigation);

        int restoredTab = savedInstanceState == null
                ? TAB_HOME
                : savedInstanceState.getInt(STATE_SELECTED_TAB, TAB_HOME);

        if (!isValidTab(restoredTab)) {
            restoredTab = TAB_HOME;
        }

        // 先设置选中状态，再注册监听器，避免初始化时触发一次无意义的 Fragment 切换。
        selectedTabId = restoredTab;
        bottomNavigation.setSelectedItemId(selectedTabId);

        setupNavigationListener();
        restoreOrCreateSelectedFragment(savedInstanceState);

        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (selectedTabId != TAB_HOME) {
                    selectTab(TAB_HOME);
                    return;
                }

                // 首页按返回键时交回系统默认行为（退出/返回上一个 Activity）。
                setEnabled(false);
                getOnBackPressedDispatcher().onBackPressed();
                setEnabled(true);
            }
        });
    }

    private void setupNavigationListener() {
        bottomNavigation.setOnItemSelectedListener(item -> selectTab(item.getItemId()));

        bottomNavigation.setOnItemReselectedListener(item -> {
            // 重复点击首页时回到顶部；其他 Tab 不重复创建、不重置状态。
            if (item.getItemId() == TAB_HOME && currentFragment instanceof HomeFragment) {
                ((HomeFragment) currentFragment).scrollToTop();
            }
        });
    }

    private void restoreOrCreateSelectedFragment(Bundle savedInstanceState) {
        FragmentManager fm = getSupportFragmentManager();
        String selectedTag = tagFor(selectedTabId);
        Fragment restored = fm.findFragmentByTag(selectedTag);

        if (restored == null) {
            // 正常首次启动，或系统恢复状态中没有当前 Tab Fragment。
            showTab(selectedTabId);
            return;
        }

        // 旋转屏幕/进程重建后，FragmentManager 会恢复已有 Fragment。
        // 这里统一校正可见性，确保只有当前 Tab 显示。
        FragmentTransaction transaction = fm.beginTransaction()
                .setReorderingAllowed(true);

        int[] tabs = {TAB_HOME, TAB_PRACTICE, TAB_RECORDS, TAB_MINE};
        for (int tab : tabs) {
            Fragment fragment = fm.findFragmentByTag(tagFor(tab));
            if (fragment == null) {
                continue;
            }
            if (tab == selectedTabId) {
                transaction.show(fragment);
            } else {
                transaction.hide(fragment);
            }
        }

        transaction.commitNow();
        currentFragment = restored;
    }

    /**
     * BottomNavigationView 的选中回调与页面切换统一走这里。
     * 返回 false 表示本次没有完成切换（例如 FragmentManager 已保存状态）。
     */
    private boolean selectTab(int tabId) {
        if (!isValidTab(tabId)) {
            return false;
        }

        if (tabId == selectedTabId && currentFragment != null) {
            return true;
        }

        FragmentManager fm = getSupportFragmentManager();
        if (fm.isStateSaved()) {
            // Activity 已进入保存状态时不提交 Fragment 事务，防止
            // IllegalStateException: Can not perform this action after onSaveInstanceState。
            return false;
        }

        showTab(tabId);
        selectedTabId = tabId;
        return true;
    }

    private void showTab(int tabId) {
        FragmentManager fm = getSupportFragmentManager();
        String targetTag = tagFor(tabId);
        Fragment target = fm.findFragmentByTag(targetTag);

        if (target == null) {
            target = createFragment(tabId);
        }

        FragmentTransaction transaction = fm.beginTransaction()
                .setReorderingAllowed(true);

        if (currentFragment != null && currentFragment.isAdded()) {
            transaction.hide(currentFragment);
        }

        if (target.isAdded()) {
            transaction.show(target);
        } else {
            transaction.add(R.id.fragmentContainer, target, targetTag);
        }

        // 不 addToBackStack：底部 Tab 是并列根页面，不应形成重复的 Tab 返回栈。
        transaction.commitNow();

        currentFragment = target;
        selectedTabId = tabId;

        if (bottomNavigation.getSelectedItemId() != tabId) {
            bottomNavigation.setSelectedItemId(tabId);
        }
    }

    private Fragment createFragment(int tabId) {
        if (tabId == TAB_HOME) {
            return new HomeFragment();
        }
        return ModuleTabFragment.newInstance(tabId);
    }

    private String tagFor(int tabId) {
        if (tabId == TAB_HOME) return "root_home";
        if (tabId == TAB_PRACTICE) return "root_practice";
        if (tabId == TAB_RECORDS) return "root_records";
        if (tabId == TAB_MINE) return "root_mine";
        throw new IllegalArgumentException("Unknown tab id: " + tabId);
    }

    private boolean isValidTab(int tabId) {
        return tabId == TAB_HOME
                || tabId == TAB_PRACTICE
                || tabId == TAB_RECORDS
                || tabId == TAB_MINE;
    }

    public void navigateToTab(int tabId) {
        if (!isValidTab(tabId)) {
            Toast.makeText(this, "暂不支持该页面", Toast.LENGTH_SHORT).show();
            return;
        }
        bottomNavigation.setSelectedItemId(tabId);
    }

    @Override
    protected void onSaveInstanceState(@NonNull Bundle outState) {
        outState.putInt(STATE_SELECTED_TAB, selectedTabId);
        super.onSaveInstanceState(outState);
    }
}
