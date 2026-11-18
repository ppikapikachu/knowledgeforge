package com.knowledgeforge.app.ui.auth;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ProgressBar;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;
import androidx.lifecycle.ViewModelProvider;

import com.google.android.material.button.MaterialButton;
import com.google.android.material.textfield.TextInputEditText;
import com.knowledgeforge.app.MainActivity;
import com.knowledgeforge.app.MyApplication;
import com.knowledgeforge.app.R;
import com.knowledgeforge.app.network.model.UserInfo;
import com.knowledgeforge.app.ui.common.Event;


public class RegisterActivity extends AppCompatActivity {

    private TextInputEditText etAccount;
    private TextInputEditText etNickname;
    private TextInputEditText etPassword;
    private TextInputEditText etConfirmPassword;

    private TextView tvError;
    private TextView tvGoLogin;

    private ProgressBar progressBar;
    private MaterialButton btnRegister;

    private RegisterViewModel viewModel;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        setContentView(R.layout.activity_register);

        initViews();
        initViewModel();
        observeViewModel();
        initListeners();
    }

    private void initViews() {
        etAccount = findViewById(R.id.etAccount);
        etNickname = findViewById(R.id.etNickname);
        etPassword = findViewById(R.id.etPassword);
        etConfirmPassword = findViewById(R.id.etConfirmPassword);

        tvError = findViewById(R.id.tvError);
        tvGoLogin = findViewById(R.id.tvGoLogin);

        progressBar = findViewById(R.id.progressBar);
        btnRegister = findViewById(R.id.btnRegister);
    }

    private void initViewModel() {

        MyApplication application =
                (MyApplication) getApplication();

        RegisterViewModelFactory factory =
                new RegisterViewModelFactory(
                        application.getAuthRepository()
                );

        viewModel = new ViewModelProvider(this, factory)
                .get(RegisterViewModel.class);
    }

    private void observeViewModel() {

        // 观察页面状态
        viewModel.getUiState().observe(this, this::render);

        // 观察注册成功事件
        viewModel.getRegisterSuccess().observe(this, event -> {

            if (event == null) {
                return;
            }

            UserInfo userInfo =
                    event.getContentIfNotHandled();

            if (userInfo != null) {
                navigateToMain();
            }
        });
    }

    /**
     * 根据 ViewModel 的状态渲染页面。
     */
    private void render(RegisterUiState state) {

        progressBar.setVisibility(
                state.isLoading() ? View.VISIBLE : View.GONE
        );

        btnRegister.setEnabled(!state.isLoading());

        if (state.hasError()) {
            tvError.setText(state.getErrorMessage());
            tvError.setVisibility(View.VISIBLE);
        } else {
            tvError.setVisibility(View.GONE);
        }
    }

    private void initListeners() {

        btnRegister.setOnClickListener(v -> {

            String account = getText(etAccount);
            String nickname = getText(etNickname);
            String password = getText(etPassword);
            String confirmPassword = getText(etConfirmPassword);

            viewModel.register(
                    account,
                    nickname,
                    password,
                    confirmPassword
            );
        });

        // 已有账号，返回登录页面
        tvGoLogin.setOnClickListener(v -> finish());
    }

    private String getText(EditText editText) {
        if (editText.getText() == null) {
            return "";
        }

        return editText.getText().toString();
    }

    /**
     * 注册成功后进入主页。
     * 注册接口已经返回 Token，不需要再调用登录接口。
     */
    private void navigateToMain() {

        Intent intent = new Intent(
                RegisterActivity.this,
                MainActivity.class
        );

        // 清空登录、注册页面栈
        intent.setFlags(
                Intent.FLAG_ACTIVITY_NEW_TASK
                        | Intent.FLAG_ACTIVITY_CLEAR_TASK
        );

        startActivity(intent);
    }
}