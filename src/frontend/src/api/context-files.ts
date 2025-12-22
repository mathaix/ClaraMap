/**
 * Context Files API client for agent file uploads.
 * Uses agent_id (InterviewAgent canonical ID) for all operations.
 */

const API_BASE = '/api/v1/context-files'

export interface ContextFile {
  id: string
  name: string
  type: string
  size: number
  status: string
  extraction_status: string | null
  uploaded_at: string
}

export interface UploadResponse {
  success: boolean
  file: ContextFile | null
  error: string | null
}

export interface ContextFileListResponse {
  files: ContextFile[]
  total: number
}

export const contextFilesApi = {
  /**
   * Upload a file for an agent's context.
   * @param agentId - The InterviewAgent ID
   */
  async uploadFile(agentId: string, file: File): Promise<UploadResponse> {
    const formData = new FormData()
    formData.append('file', file)

    const response = await fetch(`${API_BASE}/agents/${agentId}/upload`, {
      method: 'POST',
      body: formData,
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Upload failed' }))
      return {
        success: false,
        file: null,
        error: error.detail || 'Upload failed',
      }
    }

    return response.json()
  },

  /**
   * List all files for an agent.
   * @param agentId - The InterviewAgent ID
   */
  async listFiles(agentId: string): Promise<ContextFileListResponse> {
    const response = await fetch(`${API_BASE}/agents/${agentId}`)

    if (!response.ok) {
      throw new Error('Failed to list files')
    }

    return response.json()
  },

  /**
   * Delete a file.
   * @param agentId - The InterviewAgent ID
   * @param fileId - The file ID to delete
   */
  async deleteFile(agentId: string, fileId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/agents/${agentId}/files/${fileId}`, {
      method: 'DELETE',
    })

    if (!response.ok) {
      throw new Error('Failed to delete file')
    }
  },

  /**
   * Get extracted content of a file.
   * @param agentId - The InterviewAgent ID
   * @param fileId - The file ID
   */
  async getContent(
    agentId: string,
    fileId: string
  ): Promise<{ content: string | null; extraction_status: string }> {
    const response = await fetch(`${API_BASE}/agents/${agentId}/files/${fileId}/content`)

    if (!response.ok) {
      throw new Error('Failed to get file content')
    }

    return response.json()
  },
}
