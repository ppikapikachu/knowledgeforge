package com.knowledgeforge.app.ui.login;

import androidx.appcompat.app.AppCompatActivity;

import android.os.Bundle;

import com.knowledgeforge.app.MainActivity;
import com.knowledgeforge.app.R;


import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ProgressBar;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;
import androidx.lifecycle.ViewModelProvider;

import com.knowledgeforge.app.MyApplication;
import com.knowledgeforge.app.R;
import com.knowledgeforge.app.network.model.UserInfo;
import com.knowledgeforge.app.ui.auth.RegisterActivity;

public class LoginActivity extends AppCompatActivity {

    private EditText etAccount;
    private EditText etPassword;

    private Button btnLogin;

    private ProgressBar progressBar;

    private TextView tvError;

    private LoginViewModel viewModel;
    private TextView tvGoRegister ;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        setContentView(R.layout.activity_login);

        initViews();

        initViewModel();

        observeViewModel();

        initListeners();
    }

    /**
     * 初始化控件
     */
    private void initViews() {

        etAccount = findViewById(R.id.etAccount);

        etPassword = findViewById(R.id.etPassword);

        btnLogin = findViewById(R.id.btnLogin);

        progressBar = findViewById(R.id.progressBar);

        tvError = findViewById(R.id.tvError);

        tvGoRegister = findViewById(R.id.tvGoRegister);
    }

    /**
     * 初始化 ViewModel
     */
    private void initViewModel() {

        // 从 Application 获取统一创建的 Repository
        MyApplication application =
                (MyApplication) getApplication();

        // 创建 Factory
        LoginViewModelFactory factory =
                new LoginViewModelFactory(
                        application.getAuthRepository()
                );

        // 获取 ViewModel
        viewModel = new ViewModelProvider(
                this,
                factory
        ).get(LoginViewModel.class);
    }

    /**
     * 观察 ViewModel 状态
     */
    private void observeViewModel() {

        // 观察登录页面状态
        viewModel.getUiState().observe(this, state -> {

            // 加载动画
            progressBar.setVisibility(
                    state.isLoading()
                            ? View.VISIBLE
                            : View.GONE
            );

            // 登录期间禁用按钮
            btnLogin.setEnabled(!state.isLoading());

            // 显示错误信息
            if (state.hasError()) {
                // TODO: 2026/11/7  
                tvError.setText(state.getErrorMessage());

                tvError.setVisibility(View.VISIBLE);

            } else {

                tvError.setVisibility(View.GONE);
            }
        });

        // 观察登录成功事件
        viewModel.getLoginSuccess().observe(this, event -> {

            if (event == null) {
                return;
            }

            // 获取尚未消费的事件
            UserInfo user = event.getContentIfNotHandled();

            if (user == null) {
                return;
            }

            // 登录成功，进入主页面
            navigateToMain(user);
        });
    }

    /**
     * 初始化点击事件
     */
    private void initListeners() {

        tvGoRegister.setOnClickListener(v -> {
            Intent intent = new Intent(
                    LoginActivity.this,
                    RegisterActivity.class
            );

            startActivity(intent);
        });
        btnLogin.setOnClickListener(v -> {

            String account = etAccount.getText()
                    .toString();

            String password = etPassword.getText()
                    .toString();

            // Activity 不做业务校验
            // 统一交给 ViewModel
            viewModel.login(account, password);
        });
    }

    /**
     * 登录成功后的页面跳转
     */
    private void navigateToMain(UserInfo user) {
        Log.i("登录成功",user.toString());
        Intent intent = new Intent(
                LoginActivity.this,
                MainActivity.class
        );

        // 如果主页面需要，可以传递用户基础信息
        intent.putExtra("user_id", user.getId());
        intent.putExtra("account", user.getAccount());
        intent.putExtra("nickname", user.getNickname());

        startActivity(intent);

        // 防止按返回键重新回到登录页面
        finish();
    }
}