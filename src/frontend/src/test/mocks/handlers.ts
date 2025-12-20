import { http, HttpResponse } from 'msw'
import type { Project, ProjectListResponse } from '../../types/project'

const API_BASE = 'http://localhost:8000'

export const mockProjects: Project[] = [
  {
    id: 'proj_001',
    name: 'Discovery Project Alpha',
    description: 'First discovery project for testing',
    status: 'active',
    timeline_start: '2024-01-01T00:00:00Z',
    timeline_end: '2024-06-30T00:00:00Z',
    tags: ['discovery', 'enterprise'],
    created_at: '2024-01-01T10:00:00Z',
    updated_at: '2024-01-15T14:30:00Z',
    created_by: 'user_001',
  },
  {
    id: 'proj_002',
    name: 'Beta Analysis',
    description: 'Secondary project for stakeholder interviews',
    status: 'draft',
    timeline_start: null,
    timeline_end: null,
    tags: ['stakeholder'],
    created_at: '2024-02-01T09:00:00Z',
    updated_at: '2024-02-01T09:00:00Z',
    created_by: 'user_001',
  },
  {
    id: 'proj_003',
    name: 'Archived Project',
    description: 'This project has been archived',
    status: 'archived',
    timeline_start: '2023-01-01T00:00:00Z',
    timeline_end: '2023-12-31T00:00:00Z',
    tags: [],
    created_at: '2023-01-01T08:00:00Z',
    updated_at: '2024-01-01T12:00:00Z',
    created_by: 'user_002',
  },
]

export const handlers = [
  http.get(`${API_BASE}/api/v1/projects`, ({ request }) => {
    const url = new URL(request.url)
    const status = url.searchParams.get('status')
    const search = url.searchParams.get('search')

    let filtered = [...mockProjects]

    if (status) {
      filtered = filtered.filter((p) => p.status === status)
    }

    if (search) {
      const searchLower = search.toLowerCase()
      filtered = filtered.filter(
        (p) =>
          p.name.toLowerCase().includes(searchLower) ||
          p.description.toLowerCase().includes(searchLower)
      )
    }

    const response: ProjectListResponse = {
      items: filtered,
      total: filtered.length,
      limit: 50,
      offset: 0,
    }

    return HttpResponse.json(response)
  }),

  http.get(`${API_BASE}/api/v1/projects/:id`, ({ params }) => {
    const project = mockProjects.find((p) => p.id === params.id)
    if (!project) {
      return new HttpResponse(null, { status: 404 })
    }
    return HttpResponse.json(project)
  }),

  http.post(`${API_BASE}/api/v1/projects`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>
    const newProject: Project = {
      id: 'proj_new_001',
      name: body.name as string,
      description: body.description as string,
      status: 'draft',
      timeline_start: (body.timeline_start as string) || null,
      timeline_end: (body.timeline_end as string) || null,
      tags: (body.tags as string[]) || [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      created_by: 'user_001',
    }
    return HttpResponse.json(newProject, { status: 201 })
  }),

  http.patch(`${API_BASE}/api/v1/projects/:id`, async ({ params, request }) => {
    const project = mockProjects.find((p) => p.id === params.id)
    if (!project) {
      return new HttpResponse(null, { status: 404 })
    }
    const body = (await request.json()) as Record<string, unknown>
    const updated: Project = {
      ...project,
      ...(body as Partial<Project>),
      updated_at: new Date().toISOString(),
    }
    return HttpResponse.json(updated)
  }),

  http.post(`${API_BASE}/api/v1/projects/:id/archive`, ({ params }) => {
    const project = mockProjects.find((p) => p.id === params.id)
    if (!project) {
      return new HttpResponse(null, { status: 404 })
    }
    const archived: Project = {
      ...project,
      status: 'archived',
      updated_at: new Date().toISOString(),
    }
    return HttpResponse.json(archived)
  }),

  http.delete(`${API_BASE}/api/v1/projects/:id`, ({ params }) => {
    const project = mockProjects.find((p) => p.id === params.id)
    if (!project) {
      return new HttpResponse(null, { status: 404 })
    }
    return new HttpResponse(null, { status: 204 })
  }),

  http.post(`${API_BASE}/api/v1/projects/:id/duplicate`, ({ params }) => {
    const project = mockProjects.find((p) => p.id === params.id)
    if (!project) {
      return new HttpResponse(null, { status: 404 })
    }
    const duplicated: Project = {
      ...project,
      id: 'proj_dup_001',
      name: `${project.name} (Copy)`,
      status: 'draft',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    return HttpResponse.json(duplicated, { status: 201 })
  }),
]
