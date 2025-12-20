import { apiRequest } from './client'
import type {
  Project,
  ProjectCreate,
  ProjectUpdate,
  ProjectListResponse,
  ProjectListParams,
} from '../types/project'

const BASE_PATH = '/api/v1/projects'

export const projectsApi = {
  list: async (params?: ProjectListParams): Promise<ProjectListResponse> => {
    const searchParams = new URLSearchParams()
    if (params?.status) searchParams.set('status', params.status)
    if (params?.search) searchParams.set('search', params.search)
    if (params?.limit) searchParams.set('limit', params.limit.toString())
    if (params?.offset) searchParams.set('offset', params.offset.toString())

    const query = searchParams.toString()
    return apiRequest<ProjectListResponse>(`${BASE_PATH}${query ? `?${query}` : ''}`)
  },

  get: async (id: string): Promise<Project> => {
    return apiRequest<Project>(`${BASE_PATH}/${id}`)
  },

  create: async (data: ProjectCreate): Promise<Project> => {
    return apiRequest<Project>(BASE_PATH, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  update: async (id: string, data: ProjectUpdate): Promise<Project> => {
    return apiRequest<Project>(`${BASE_PATH}/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  },

  archive: async (id: string): Promise<Project> => {
    return apiRequest<Project>(`${BASE_PATH}/${id}/archive`, {
      method: 'POST',
    })
  },

  delete: async (id: string): Promise<void> => {
    return apiRequest<void>(`${BASE_PATH}/${id}`, {
      method: 'DELETE',
    })
  },

  duplicate: async (id: string): Promise<Project> => {
    return apiRequest<Project>(`${BASE_PATH}/${id}/duplicate`, {
      method: 'POST',
    })
  },
}
