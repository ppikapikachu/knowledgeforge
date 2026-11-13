package com.knowledgeforge.app.ui.practice;

import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;
import androidx.fragment.app.FragmentManager;

import com.knowledgeforge.app.MainActivity;
import com.knowledgeforge.app.R;
import com.knowledgeforge.app.network.model.QuestionBank;

/**
 * 练习 Tab 根容器。内部使用 childFragmentManager 管理「入口页 → 组卷配置页」，
 * 不会影响 MainActivity 管理的四个底部 Tab 根 Fragment。
 */
public class PracticeFragment extends Fragment {

    private static final String TAG_LANDING = "practice_landing";
    private static final String TAG_ASSEMBLE = "practice_assemble";

    public PracticeFragment() { }

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater,
                             @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_practice_host, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);
        FragmentManager childManager = getChildFragmentManager();
        if (childManager.findFragmentById(R.id.practiceChildContainer) == null) {
            childManager.beginTransaction()
                    .setReorderingAllowed(true)
                    .add(R.id.practiceChildContainer, new PracticeLandingFragment(), TAG_LANDING)
                    .commitNow();
        }
        updateBottomNavigationVisibility();
    }

    @Override
    public void onResume() {
        super.onResume();
        updateBottomNavigationVisibility();
    }

    public void syncNavigationVisibility() {
        updateBottomNavigationVisibility();
    }

    private void updateBottomNavigationVisibility() {
        if (getActivity() instanceof MainActivity) {
            Fragment current = getChildFragmentManager().findFragmentById(R.id.practiceChildContainer);
            ((MainActivity) getActivity()).setBottomNavigationVisible(!(current instanceof AssemblePaperFragment));
        }
    }

    public void openAssemble(QuestionBank bank) {
        openAssemble(bank == null ? -1 : bank.getId());
    }

    public void openAssemble(int selectedBankId) {
        if (!isAdded()) return;
        FragmentManager fm = getChildFragmentManager();
        if (fm.isStateSaved()) return;
        fm.beginTransaction()
                .setReorderingAllowed(true)
                .replace(R.id.practiceChildContainer,
                        AssemblePaperFragment.newInstance(selectedBankId), TAG_ASSEMBLE)
                .addToBackStack(TAG_ASSEMBLE)
                .commit();
        if (getActivity() instanceof MainActivity) {
            ((MainActivity) getActivity()).setBottomNavigationVisible(false);
        }
    }

    /** MainActivity 返回键先询问本容器，组卷页优先退回练习入口页。 */
    public boolean handleBackPressed() {
        FragmentManager fm = getChildFragmentManager();
        if (fm.isStateSaved() || fm.getBackStackEntryCount() == 0) return false;
        Fragment current = fm.findFragmentById(R.id.practiceChildContainer);
        if (current instanceof AssemblePaperFragment && ((AssemblePaperFragment) current).isAssembling()) {
            if (getContext() != null) {
                Toast.makeText(requireContext(), "正在生成试卷，请稍候完成后再返回", Toast.LENGTH_SHORT).show();
            }
            return true;
        }
        boolean popped = fm.popBackStackImmediate();
        if (popped) {
            Fragment landing = fm.findFragmentByTag(TAG_LANDING);
            if (landing instanceof PracticeLandingFragment) {
                ((PracticeLandingFragment) landing).refreshData();
            }
            if (getActivity() instanceof MainActivity) {
                ((MainActivity) getActivity()).setBottomNavigationVisible(true);
            }
        }
        return popped;
    }

    public void scrollToTop() {
        Fragment fragment = getChildFragmentManager().findFragmentByTag(TAG_LANDING);
        if (fragment instanceof PracticeLandingFragment) {
            ((PracticeLandingFragment) fragment).scrollToTop();
        }
    }
}
