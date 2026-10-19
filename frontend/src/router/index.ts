import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { getToken } from '@/utils/storage'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/LoginView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('@/layouts/AdminLayout.vue'),
    meta: { requiresAuth: true },
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/DashboardView.vue'),
        meta: { title: 'Dashboard' },
      },
      {
        path: 'knowledge-bases',
        name: 'KnowledgeBases',
        component: () => import('@/views/knowledge/KnowledgeBaseView.vue'),
        meta: { title: '知识库管理' },
      },
      {
        path: 'knowledge',
        name: 'KnowledgeList',
        component: () => import('@/views/knowledge/KnowledgeList.vue'),
        meta: { title: '知识点管理' },
      },
      {
        path: 'knowledge/create',
        name: 'KnowledgeCreate',
        component: () => import('@/views/knowledge/KnowledgeForm.vue'),
        meta: { title: '新增知识点' },
      },
      {
        path: 'knowledge/:id',
        name: 'KnowledgeDetail',
        component: () => import('@/views/knowledge/KnowledgeDetail.vue'),
        meta: { title: '知识点详情' },
      },
      {
        path: 'knowledge/:id/edit',
        name: 'KnowledgeEdit',
        component: () => import('@/views/knowledge/KnowledgeForm.vue'),
        meta: { title: '编辑知识点' },
      },
      {
        path: 'knowledge-relations',
        name: 'KnowledgeRelations',
        component: () => import('@/views/knowledge/KnowledgeRelations.vue'),
        meta: { title: '知识关系' },
      },
      {
        path: 'question-management/generate',
        name: 'QuestionGenerate',
        component: () => import('@/views/question-management/GenerateQuestionView.vue'),
        meta: { title: 'AI 生成题目' },
      },
      {
        path: 'question-management/tasks',
        name: 'GenerationTaskList',
        component: () => import('@/views/question-management/GenerationTaskListView.vue'),
        meta: { title: '生成任务' },
      },
      {
        path: 'question-management/tasks/:taskId',
        name: 'GenerationTaskDetail',
        component: () => import('@/views/question-management/GenerationTaskDetailView.vue'),
        meta: { title: '任务详情' },
      },
      {
        path: 'question-management/review',
        name: 'QuestionReview',
        component: () => import('@/views/question-management/QuestionReviewView.vue'),
        meta: { title: '题目审核' },
      },
      {
        path: 'question-management/questions',
        name: 'QuestionManageList',
        component: () => import('@/views/question-management/QuestionListView.vue'),
        meta: { title: '题目列表' },
      },
      {
        path: 'question-management/questions/:questionId',
        name: 'QuestionManageDetail',
        component: () => import('@/views/question-management/QuestionDetailView.vue'),
        meta: { title: '题目详情' },
      },
      {
        path: 'questions',
        name: 'QuestionList',
        component: () => import('@/views/question/QuestionList.vue'),
        meta: { title: '题目管理' },
      },
      {
        path: 'questions/create',
        name: 'QuestionCreate',
        component: () => import('@/views/question/QuestionForm.vue'),
        meta: { title: '新增题目' },
      },
      {
        path: 'questions/:id',
        name: 'QuestionDetail',
        component: () => import('@/views/question/QuestionDetail.vue'),
        meta: { title: '题目详情' },
      },
      {
        path: 'questions/:id/edit',
        name: 'QuestionEdit',
        component: () => import('@/views/question/QuestionForm.vue'),
        meta: { title: '编辑题目' },
      },
      {
        path: 'import-tasks',
        name: 'ImportTaskList',
        component: () => import('@/views/import-task/ImportTaskList.vue'),
        meta: { title: '导入任务' },
      },
      {
        path: 'import-tasks/:id',
        name: 'ImportTaskDetail',
        component: () => import('@/views/import-task/ImportTaskDetail.vue'),
        meta: { title: '任务详情' },
      },
      {
        path: 'admin',
        name: 'Admin',
        component: () => import('@/views/admin/AdminView.vue'),
        meta: { title: '管理员' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard',
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

// Navigation guard
router.beforeEach((to, _from, next) => {
  const token = getToken()
  const requiresAuth = to.matched.some((record) => record.meta.requiresAuth !== false)

  if (requiresAuth && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router
