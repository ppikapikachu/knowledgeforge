package com.knowledgeforge.app;

import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.view.View;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.fragment.app.Fragment;
import androidx.navigation.NavController;
import androidx.navigation.NavDestination;
import androidx.navigation.fragment.NavHostFragment;
import androidx.navigation.ui.NavigationUI;

import com.google.android.material.bottomnavigation.BottomNavigationView;
import com.knowledgeforge.app.network.ApiClient;
import com.knowledgeforge.app.network.auth.AuthSessionEventManager;
import com.knowledgeforge.app.ui.home.HomeFragment;
import com.knowledgeforge.app.ui.login.LoginActivity;
import com.knowledgeforge.app.ui.practice.PracticeLandingFragment;

/**
 * KnowledgeForge 主容器。
 *
 * 主导航使用 Navigation Component：
 * 1. BottomNavigationView 通过 setupWithNavController() 绑定 NavController；
 * 2. 四个 Tab 分别是 main_nav_graph 中的嵌套导航图，彼此拥有独立返回栈；
 * 3. Navigation 2.4.0+ 自动保存/恢复多返回栈；
 * 4. 系统返回由 NavController 根据当前返回栈自动处理；
 * 5. 只有组卷请求进行中时，由 AssemblePaperFragment 临时拦截返回。
 *    业务逻辑、ViewModel、Repository 和页面布局保持原样。
 */
public class MainActivity extends AppCompatActivity {

    public static final int TAB_HOME = R.id.nav_home;
    public static final int TAB_PRACTICE = R.id.nav_practice;
    public static final int TAB_RECORDS = R.id.nav_records;
    public static final int TAB_MINE = R.id.nav_mine;

    private BottomNavigationView bottomNavigation;
    private NavHostFragment navHostFragment;
    private NavController navController;
    private NavDestination previousDestination;
    /**
     * 登录失效事件监听器。
     */
    private final AuthSessionEventManager.Listener authListener =
            this::handleSessionExpired;
    private boolean redirectingToLogin = false;

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

        // 练习入口页显示底部导航；组卷等练习子页面隐藏底部导航。
        // 系统返回不在 Activity 中手动处理：NavController 会自动弹出当前返回栈。
        // 当从练习子页面返回入口时，通知入口页刷新数据，保持原有返回后的刷新行为。
        navController.addOnDestinationChangedListener((controller, destination, arguments) -> {
            if (previousDestination != null
                    && destination.getId() == R.id.practiceLandingFragment
                    && previousDestination.getId() != R.id.practiceLandingFragment
                    && findTopLevelTabId(previousDestination) == TAB_PRACTICE) {
                androidx.navigation.NavBackStackEntry landingEntry =
                        controller.getCurrentBackStackEntry();
                if (landingEntry != null) {
                    landingEntry.getSavedStateHandle().set(
                            PracticeLandingFragment.RESULT_KEY_REFRESH, true);
                }
            }
            previousDestination = destination;

            int tabId = findTopLevelTabId(destination);
            if (tabId != TAB_PRACTICE) {
                setBottomNavigationVisible(true);
                return;
            }

            boolean isPracticeLanding = destination.getId() == R.id.practiceLandingFragment;
            setBottomNavigationVisible(isPracticeLanding);
        });
    }
    @Override
    protected void onStart() {
        super.onStart();

        // 页面进入前台时注册监听。
        AuthSessionEventManager.addListener(authListener);
    }
    @Override
    protected void onStop() {

        // 页面离开前台时注销，避免 Activity 泄漏。
        AuthSessionEventManager.removeListener(authListener);

        super.onStop();
    }

    /**
     * 收到登录失效事件后，清除登录状态并跳转登录页。
     */
    private void handleSessionExpired() {

        runOnUiThread(() -> {

            // 防止重复跳转。
            if (redirectingToLogin || isFinishing() || isDestroyed()) {
                return;
            }

            redirectingToLogin = true;

            // 清除本地 Token。
            ApiClient.getInstance(getApplicationContext())
                    .getTokenStorage()
                    .clearSession();

            Toast.makeText(
                    this,
                    "登录状态已失效，请重新登录",
                    Toast.LENGTH_LONG
            ).show();

            Intent intent = new Intent(
                    MainActivity.this,
                    LoginActivity.class
            );

            // 清空当前 Activity 返回栈。
            intent.setFlags(
                    Intent.FLAG_ACTIVITY_NEW_TASK
                            | Intent.FLAG_ACTIVITY_CLEAR_TASK
            );

            startActivity(intent);
            finish();
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
        } else if (tabId == TAB_PRACTICE && currentFragment instanceof PracticeLandingFragment) {
            ((PracticeLandingFragment) currentFragment).scrollToTop();
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

    private int getTabRootDestinationId(int tabId) {
        if (tabId == TAB_HOME) return R.id.homeFragment;
        if (tabId == TAB_PRACTICE) return R.id.practiceLandingFragment;
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
