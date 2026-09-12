import axios from 'axios'
import type { AxiosInstance, InternalAxiosRequestConfig, AxiosResponse } from 'axios'
import { getToken, removeToken } from './storage'
import { ElMessage } from 'element-plus'
import router from '@/router'

const request: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  },
)

// Response interceptor
request.interceptors.response.use(
  (response: AxiosResponse) => {
    const { data } = response
    // Unified response: { code: 0, message: 'success', data: {} }
    if (data.code === 0) {
      return data
    }
    // Error response from backend
    const errMsg = data.message || '请求失败'
    try {
      ElMessage.error(errMsg)
    } catch {
      // Ignore ElMessage error
    }
    return Promise.reject(new Error(errMsg))
  },
  (error) => {
    const { response } = error
    let errMsg = '请求失败'
    if (response) {
      switch (response.status) {
        case 401:
          removeToken()
          router.push('/login')
          errMsg = '登录已过期，请重新登录'
          break
        case 403:
          errMsg = '权限不足'
          break
        case 404:
          errMsg = '请求的资源不存在'
          break
        case 409:
          errMsg = '数据已存在'
          break
        case 422:
          errMsg = '请求参数错误'
          break
        case 500:
          errMsg = '服务器内部错误'
          break
        default:
          errMsg = response.data?.message || '请求失败'
      }
    } else {
      errMsg = '网络错误，请检查后端服务是否启动'
    }
    try {
      ElMessage.error(errMsg)
    } catch {
      // Ignore ElMessage error
    }
    return Promise.reject(error)
  },
)

export default request
