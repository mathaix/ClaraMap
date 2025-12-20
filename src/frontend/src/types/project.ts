export type ProjectStatus = 'draft' | 'active' | 'completed' | 'archived';

export interface Project {
  id: string;
  name: string;
  description: string;
  status: ProjectStatus;
  timeline_start: string | null;
  timeline_end: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
  created_by: string;
}

export interface ProjectCreate {
  name: string;
  description: string;
  timeline_start?: string | null;
  timeline_end?: string | null;
  tags?: string[];
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  status?: ProjectStatus;
  timeline_start?: string | null;
  timeline_end?: string | null;
  tags?: string[];
}

export interface ProjectListResponse {
  items: Project[];
  total: number;
  limit: number;
  offset: number;
}

export interface ProjectListParams {
  status?: ProjectStatus;
  search?: string;
  limit?: number;
  offset?: number;
}
