import { useState } from 'react'
import {
  useProjects,
  useCreateProject,
  useArchiveProject,
  useDeleteProject,
  useDuplicateProject,
} from '../hooks/useProjects'
import { ProjectCard } from '../components/ProjectCard'
import { CreateProjectModal } from '../components/CreateProjectModal'
import type { ProjectStatus, ProjectCreate } from '../types/project'

export default function ProjectsPage() {
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [statusFilter, setStatusFilter] = useState<ProjectStatus | ''>('')
  const [search, setSearch] = useState('')

  const { data, isLoading, error } = useProjects({
    status: statusFilter || undefined,
    search: search || undefined,
  })

  const createMutation = useCreateProject()
  const archiveMutation = useArchiveProject()
  const deleteMutation = useDeleteProject()
  const duplicateMutation = useDuplicateProject()

  const handleCreate = (projectData: ProjectCreate) => {
    createMutation.mutate(projectData, {
      onSuccess: () => setIsCreateOpen(false),
    })
  }

  const handleArchive = (id: string) => {
    if (confirm('Are you sure you want to archive this project?')) {
      archiveMutation.mutate(id)
    }
  }

  const handleDelete = (id: string) => {
    if (confirm('Are you sure you want to delete this project? This cannot be undone.')) {
      deleteMutation.mutate(id)
    }
  }

  const handleDuplicate = (id: string) => {
    duplicateMutation.mutate(id)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Projects</h2>
        <button
          onClick={() => setIsCreateOpen(true)}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700"
        >
          New Project
        </button>
      </div>

      <div className="flex gap-4 mb-6">
        <input
          type="text"
          placeholder="Search projects..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 max-w-xs rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as ProjectStatus | '')}
          className="rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="">All Status</option>
          <option value="draft">Draft</option>
          <option value="active">Active</option>
          <option value="completed">Completed</option>
          <option value="archived">Archived</option>
        </select>
      </div>

      {isLoading && (
        <div className="text-center py-12 text-gray-500">Loading projects...</div>
      )}

      {error && (
        <div className="text-center py-12 text-red-600">
          Failed to load projects. Please try again.
        </div>
      )}

      {data && data.items.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          No projects found. Create your first project to get started.
        </div>
      )}

      {data && data.items.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {data.items.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onArchive={handleArchive}
              onDelete={handleDelete}
              onDuplicate={handleDuplicate}
            />
          ))}
        </div>
      )}

      <CreateProjectModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onSubmit={handleCreate}
        isLoading={createMutation.isPending}
      />
    </div>
  )
}
