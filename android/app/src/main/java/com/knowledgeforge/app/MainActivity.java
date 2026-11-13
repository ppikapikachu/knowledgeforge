package com.knowledgeforge.app;

import android.graphics.Color;
import android.os.Bundle;
import android.view.View;
import android.widget.Toast;

import androidx.activity.OnBackPressedCallback;
import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.fragment.app.Fragment;
import androidx.navigation.NavController;
import androidx.navigation.NavDestination;
import androidx.navigation.NavGraph;
import androidx.navigation.fragment.NavHostFragment;
import androidx.navigation.ui.NavigationUI;

import com.google.android.material.bottomnavigation.BottomNavigationView;
import com.knowledgeforge.app.ui.home.HomeFragment;
import com.knowledgeforge.app.ui.practice.PracticeFragment;

/**
 * KnowledgeForge 主容器。
 *
 * 主导航使用 Navigation Component：
 * 1. BottomNavigationView 通过 setupWithNavController() 绑定 NavController；
 * 2. 四个 Tab 分别是 main_nav_graph 中的嵌套导航图，彼此拥有独立返回栈；
 * 3. Navigation 2.4.0+ 自动保存/恢复多返回栈；
 * 4. 练习 Tab 内部当前仍由 PracticeFragment 的 childFragmentManager 管理入口页与组卷页，
 *    本次只替换主底部导航，不改动练习页已有业务与页面实现。
 */
public class MainActivity extends AppCompatActivity {

    public static final int TAB_HOME = R.id.nav_home;
    public static final int TAB_PRACTICE = R.id.nav_practice;
    public static final int TAB_RECORDS = R.id.nav_records;
    public static final int TAB_MINE = R.id.nav_mine;

    private BottomNavigationView bottomNavigation;
    private NavHostFragment navHostFragment;
    private NavController navController;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        // 状态栏与首页/练习页的浅紫色背景保持一致。
        getWindow().setStatusBarColor(Color.rgb(234, 230, 255));
        getWindow().getDecorView().setSystemUiVisibility(
                getWindow().getDecorView().getSystemUiVisibility()
                        | View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
        );

        bottomNavigation = findViewById(R.id.bottomNavigation);
        navHostFragment = (NavHostFragment) getSupportFragmentManager()
                .findFragmentById(R.id.navHostFragment);

        if (navHostFragment == null) {
            throw new IllegalStateException("activity_main.xml 未配置 NavHostFragment");
        }

        navController = navHostFragment.getNavController();

        // 主导航的选中状态、Tab 切换、多返回栈均交给 NavigationUI 管理。
        NavigationUI.setupWithNavController(bottomNavigation, navController);

        // 重复点击当前 Tab：返回该 Tab 根页面，并对首页/练习页执行回顶。
        bottomNavigation.setOnItemReselectedListener(item -> handleTabReselected(item.getItemId()));

        // 组卷页属于练习 Tab 内部页面，隐藏主底部导航；返回入口页后恢复。
        navController.addOnDestinationChangedListener((controller, destination, arguments) -> {
            // destination 就是当前的新页面
            int tabId = findTopLevelTabId(destination);
            if (tabId != TAB_PRACTICE) {
                setBottomNavigationVisible(true);
                return;
            }

            Fragment currentFragment = getCurrentNavHostFragment();
            if (currentFragment instanceof PracticeFragment) {
                ((PracticeFragment) currentFragment).syncNavigationVisibility();
            }
        });

        // 维持原来的返回体验：练习内部页先返回入口；其他 Tab 根页面返回首页；首页再退出。
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                Fragment currentFragment = getCurrentNavHostFragment();

                // 练习 Tab 的组卷配置页由其 childFragmentManager 管理，先处理内部返回。
                if (currentFragment instanceof PracticeFragment
                        && ((PracticeFragment) currentFragment).handleBackPressed()) {
                    return;
                }

                NavDestination destination = navController.getCurrentDestination();
                if (destination == null) {
                    finish();
                    return;
                }

                int currentTabId = findTopLevelTabId(destination);

                // 若当前在某个 Tab 的详情页，先弹出该 Tab 内部的 Navigation 返回栈。
                if (!isAtTabStartDestination(destination, currentTabId)) {
                    if (navController.popBackStack()) {
                        return;
                    }
                }

                // 在非首页 Tab 根页面按返回，先切回首页。
                if (currentTabId != TAB_HOME) {
                    selectTab(TAB_HOME);
                    return;
                }

                // 首页根页面交给系统处理（退出或返回上一个 Activity）。
                setEnabled(false);
                try {
                    getOnBackPressedDispatcher().onBackPressed();
                } finally {
                    setEnabled(true);
                }
            }
        });
    }

    /**
     * 保留首页快捷入口等现有调用方式。
     * 菜单项 ID 与顶层嵌套 Navigation Graph ID 一致。
     */
    public void navigateToTab(int tabId) {
        if (!isValidTab(tabId)) {
            Toast.makeText(this, "暂不支持该页面", Toast.LENGTH_SHORT).show();
            return;
        }
        selectTab(tabId);
    }

    private void selectTab(int tabId) {
        if (bottomNavigation == null || !isValidTab(tabId)) {
            return;
        }
        if (bottomNavigation.getSelectedItemId() != tabId) {
            // setupWithNavController 注册的菜单监听会执行实际导航。
            bottomNavigation.setSelectedItemId(tabId);
        }
    }

    private void handleTabReselected(int tabId) {
        int rootDestinationId = getTabRootDestinationId(tabId);
        if (rootDestinationId != 0) {
            // 当前 Tab 如果已经进入后续详情页，重复点击 Tab 时回到该 Tab 根页面。
            navController.popBackStack(rootDestinationId, false);
        }

        Fragment currentFragment = getCurrentNavHostFragment();
        if (tabId == TAB_HOME && currentFragment instanceof HomeFragment) {
            ((HomeFragment) currentFragment).scrollToTop();
        } else if (tabId == TAB_PRACTICE && currentFragment instanceof PracticeFragment) {
            ((PracticeFragment) currentFragment).scrollToTop();
        }
    }

    private Fragment getCurrentNavHostFragment() {
        if (navHostFragment == null) {
            return null;
        }
        return navHostFragment.getChildFragmentManager().getPrimaryNavigationFragment();
    }

    /** 查找当前目的地所属的顶层 Tab Graph。 */
    private int findTopLevelTabId(@NonNull NavDestination destination) {
        NavDestination current = destination;
        while (current != null) {
            int id = current.getId();
            if (isValidTab(id)) {
                return id;
            }
            current = current.getParent();
        }
        return TAB_HOME;
    }

    /** 当前目的地是否就是该 Tab Graph 的 startDestination。 */
    private boolean isAtTabStartDestination(@NonNull NavDestination destination, int tabId) {
        NavDestination current = destination;
        while (current != null) {
            if (current.getId() == tabId && current instanceof NavGraph) {
                return destination.getId() == ((NavGraph) current).getStartDestinationId();
            }
            current = current.getParent();
        }
        return true;
    }

    private int getTabRootDestinationId(int tabId) {
        if (tabId == TAB_HOME) return R.id.homeFragment;
        if (tabId == TAB_PRACTICE) return R.id.practiceFragment;
        if (tabId == TAB_RECORDS) return R.id.recordsFragment;
        if (tabId == TAB_MINE) return R.id.mineFragment;
        return 0;
    }

    private boolean isValidTab(int tabId) {
        return tabId == TAB_HOME
                || tabId == TAB_PRACTICE
                || tabId == TAB_RECORDS
                || tabId == TAB_MINE;
    }

    /** 供练习 Tab 内部页面控制主底部导航显隐。 */
    public void setBottomNavigationVisible(boolean visible) {
        if (bottomNavigation != null) {
            bottomNavigation.setVisibility(visible ? View.VISIBLE : View.GONE);
        }
    }
}
