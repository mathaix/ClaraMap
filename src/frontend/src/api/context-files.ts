/**
 * Context Files API client for agent file uploads.
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
   */
  async uploadFile(
    sessionId: string,
    agentIndex: number,
    file: File
  ): Promise<UploadResponse> {
    const formData = new FormData()
    formData.append('file', file)

    const response = await fetch(
      `${API_BASE}/sessions/${sessionId}/agents/${agentIndex}/upload`,
      {
        method: 'POST',
        body: formData,
      }
    )

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
   */
  async listFiles(sessionId: string, agentIndex: number): Promise<ContextFileListResponse> {
    const response = await fetch(
      `${API_BASE}/sessions/${sessionId}/agents/${agentIndex}`
    )

    if (!response.ok) {
      throw new Error('Failed to list files')
    }

    return response.json()
  },

  /**
   * Delete a file.
   */
  async deleteFile(
    sessionId: string,
    agentIndex: number,
    fileId: string
  ): Promise<void> {
    const response = await fetch(
      `${API_BASE}/sessions/${sessionId}/agents/${agentIndex}/files/${fileId}`,
      { method: 'DELETE' }
    )

    if (!response.ok) {
      throw new Error('Failed to delete file')
    }
  },

  /**
   * Get extracted content of a file.
   */
  async getContent(
    sessionId: string,
    agentIndex: number,
    fileId: string
  ): Promise<{ content: string | null; extraction_status: string }> {
    const response = await fetch(
      `${API_BASE}/sessions/${sessionId}/agents/${agentIndex}/files/${fileId}/content`
    )

    if (!response.ok) {
      throw new Error('Failed to get file content')
    }

    return response.json()
  },
}
