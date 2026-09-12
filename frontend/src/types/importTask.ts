export interface ImportTask {
  id: number
  file_name: string
  file_path: string
  file_size: number
  file_type: string
  status: string
  progress: number
  current_step: string | null
  error_message: string | null
  created_by: number
  started_at: string | null
  finished_at: string | null
  created_at: string
  updated_at: string
}

export interface ImportTaskQueryParams {
  page?: number
  page_size?: number
  status?: string | null
}
