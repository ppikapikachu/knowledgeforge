import axios from 'axios'
import type { AxiosInstance, InternalAxiosRequestConfig, AxiosResponse } from 'axios'
import { getToken, removeToken } from './storage'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { ApiError, API_CODE } from '@/types/api'

export { ApiError, API_CODE } from '@/types/api'

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
    // 认证失效（也可能出现在 2xx 响应中）
    if (data.code === API_CODE.UNAUTHORIZED) {
      removeToken()
      router.push('/login')
    }
    // 业务错误：HTTP 2xx 但 code ≠ 0
    const errMsg = data.message || '请求失败'
    try {
      ElMessage.error(errMsg)
    } catch {
      // Ignore ElMessage error
    }
    return Promise.reject(new ApiError(errMsg, data.code, data.data, response.status))
  },
  (error) => {
    const { response } = error

    // 认证失效：HTTP 401 或 envelope code 40101
    if (
      response?.status === 401 ||
      response?.data?.code === API_CODE.UNAUTHORIZED
    ) {
      removeToken()
      router.push('/login')
      const msg = '登录已过期，请重新登录'
      try {
        ElMessage.error(msg)
      } catch {
        // Ignore
      }
      return Promise.reject(
        new ApiError(msg, API_CODE.UNAUTHORIZED, response?.data?.data, response?.status),
      )
    }

    let errMsg = '请求失败'
    let code = response?.data?.code ?? -1

    if (response) {
      switch (response.status) {
        case 403:
          errMsg = response.data?.message || (getToken() ? '权限不足' : '请先登录')
          break
        case 422:
          errMsg = response.data?.message || '请求参数错误'
          break
        case 500:
          errMsg = response.data?.message || '服务器内部错误'
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
    return Promise.reject(new ApiError(errMsg, code, response?.data?.data, response?.status))
  },
)

export default request
