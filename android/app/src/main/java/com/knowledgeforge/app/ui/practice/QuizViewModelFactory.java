package com.knowledgeforge.app.ui.practice;

import androidx.annotation.NonNull;
import androidx.lifecycle.ViewModel;
import androidx.lifecycle.ViewModelProvider;

import com.knowledgeforge.app.data.repository.PracticeRepository;

/**
 * QuizViewModel 工厂。
 *
 * <p>因为 QuizViewModel 需要 PracticeRepository 和 QuizTimerStorage 两个构造参数，
 * 默认 ViewModelProvider.Factory 无法自动创建，所以由本工厂负责注入。</p>
 */
public class QuizViewModelFactory implements ViewModelProvider.Factory {

    /** 刷题数据仓库，内部复用现有 Retrofit/OkHttp。 */
    private final PracticeRepository repository;
    /** 刷题计时本地存储。 */
    private final QuizTimerStorage timerStorage;

    /** 保存 ViewModel 创建所需的依赖。 */
    public QuizViewModelFactory(PracticeRepository repository, QuizTimerStorage timerStorage) {
        this.repository = repository;
        this.timerStorage = timerStorage;
    }

    /** 根据请求的 ViewModel 类型创建 QuizViewModel。 */
    @NonNull
    @Override
    @SuppressWarnings("unchecked")
    public <T extends ViewModel> T create(@NonNull Class<T> modelClass) {
        if (modelClass.isAssignableFrom(QuizViewModel.class)) {
            return (T) new QuizViewModel(repository, timerStorage);
        }
        throw new IllegalArgumentException("Unknown ViewModel class: " + modelClass.getName());
    }
}
