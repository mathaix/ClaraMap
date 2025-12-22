import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { format } from 'date-fns'
import clsx from 'clsx'
import {
  useProject,
  useUpdateProject,
  useArchiveProject,
  useDeleteProject,
} from '../hooks/useProjects'
import { designSessionsApi } from '../api/design-sessions'
import type { ProjectStatus, ProjectUpdate } from '../types/project'
import type { SessionStateResponse } from '../types/design-session'

const statusStyles: Record<ProjectStatus, string> = {
  draft: 'bg-gray-100 text-gray-700',
  active: 'bg-green-100 text-green-700',
  completed: 'bg-blue-100 text-blue-700',
  archived: 'bg-yellow-100 text-yellow-700',
}

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const { data: project, isLoading, error } = useProject(projectId!)

  const [isEditing, setIsEditing] = useState(false)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editStatus, setEditStatus] = useState<ProjectStatus>('draft')
  const [editTags, setEditTags] = useState('')
  const [designSession, setDesignSession] = useState<SessionStateResponse | null>(null)

  // Fetch design session to check if we have a blueprint
  useEffect(() => {
    if (!projectId) return
    designSessionsApi.getByProject(projectId).then(setDesignSession).catch(() => {})
  }, [projectId])

  // Check if we have agents in the blueprint (meaning simulation is available)
  const hasBlueprint = (designSession?.blueprint_state?.agents?.length ?? 0) > 0

  const updateMutation = useUpdateProject()
  const archiveMutation = useArchiveProject()
  const deleteMutation = useDeleteProject()

  const startEditing = () => {
    if (project) {
      setEditName(project.name)
      setEditDescription(project.description)
      setEditStatus(project.status)
      setEditTags(project.tags.join(', '))
      setIsEditing(true)
    }
  }

  const handleSave = () => {
    if (!projectId) return

    const updates: ProjectUpdate = {}
    if (editName !== project?.name) updates.name = editName
    if (editDescription !== project?.description) updates.description = editDescription
    if (editStatus !== project?.status) updates.status = editStatus

    const newTags = editTags
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean)
    if (JSON.stringify(newTags) !== JSON.stringify(project?.tags)) {
      updates.tags = newTags
    }

    if (Object.keys(updates).length > 0) {
      updateMutation.mutate(
        { id: projectId, data: updates },
        { onSuccess: () => setIsEditing(false) }
      )
    } else {
      setIsEditing(false)
    }
  }

  const handleArchive = () => {
    if (projectId && confirm('Are you sure you want to archive this project?')) {
      archiveMutation.mutate(projectId)
    }
  }

  const handleDelete = () => {
    if (
      projectId &&
      confirm('Are you sure you want to delete this project? This cannot be undone.')
    ) {
      deleteMutation.mutate(projectId, {
        onSuccess: () => navigate('/projects'),
      })
    }
  }

  if (isLoading) {
    return <div className="text-center py-12 text-gray-500">Loading project...</div>
  }

  if (error || !project) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600 mb-4">Failed to load project.</p>
        <Link to="/projects" className="text-blue-600 hover:underline">
          Back to Projects
        </Link>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-6">
        <Link
          to="/projects"
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          &larr; Back to Projects
        </Link>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        {isEditing ? (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Name</label>
              <input
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Description
              </label>
              <textarea
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                rows={3}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Status</label>
              <select
                value={editStatus}
                onChange={(e) => setEditStatus(e.target.value as ProjectStatus)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="draft">Draft</option>
                <option value="active">Active</option>
                <option value="completed">Completed</option>
                <option value="archived">Archived</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Tags (comma-separated)
              </label>
              <input
                type="text"
                value={editTags}
                onChange={(e) => setEditTags(e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
            <div className="flex gap-3">
              <button
                onClick={handleSave}
                disabled={updateMutation.isPending}
                className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                {updateMutation.isPending ? 'Saving...' : 'Save'}
              </button>
              <button
                onClick={() => setIsEditing(false)}
                className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-md"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="flex items-start justify-between mb-4">
              <div>
                <h2 className="text-2xl font-bold text-gray-900">{project.name}</h2>
                <span
                  className={clsx(
                    'mt-2 inline-block px-2.5 py-0.5 rounded-full text-xs font-medium capitalize',
                    statusStyles[project.status]
                  )}
                >
                  {project.status}
                </span>
              </div>
              <div className="flex gap-2">
                <Link
                  to={`/projects/${projectId}/design`}
                  className="px-4 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md"
                >
                  Design Blueprint
                </Link>
                <button
                  onClick={startEditing}
                  className="px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-md border border-gray-300"
                >
                  Edit
                </button>
                {project.status !== 'archived' && (
                  <button
                    onClick={handleArchive}
                    className="px-3 py-1.5 text-sm font-medium text-yellow-700 hover:bg-yellow-50 rounded-md border border-yellow-300"
                  >
                    Archive
                  </button>
                )}
                <button
                  onClick={handleDelete}
                  className="px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50 rounded-md border border-red-300"
                >
                  Delete
                </button>
              </div>
            </div>

            <p className="text-gray-600 mb-4">{project.description}</p>

            {project.tags.length > 0 && (
              <div className="flex flex-wrap gap-1 mb-4">
                {project.tags.map((tag) => (
                  <span
                    key={tag}
                    className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}

            <div className="border-t border-gray-200 pt-4 mt-4 grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-gray-500">Created:</span>{' '}
                <span className="text-gray-900">
                  {format(new Date(project.created_at), 'MMM d, yyyy h:mm a')}
                </span>
              </div>
              <div>
                <span className="text-gray-500">Updated:</span>{' '}
                <span className="text-gray-900">
                  {format(new Date(project.updated_at), 'MMM d, yyyy h:mm a')}
                </span>
              </div>
              {project.timeline_start && (
                <div>
                  <span className="text-gray-500">Start Date:</span>{' '}
                  <span className="text-gray-900">
                    {format(new Date(project.timeline_start), 'MMM d, yyyy')}
                  </span>
                </div>
              )}
              {project.timeline_end && (
                <div>
                  <span className="text-gray-500">End Date:</span>{' '}
                  <span className="text-gray-900">
                    {format(new Date(project.timeline_end), 'MMM d, yyyy')}
                  </span>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* Interview Agents Section */}
      <div className="mt-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Interview Agents</h3>
          {!hasBlueprint && (
            <Link
              to={`/projects/${projectId}/design`}
              className="text-sm text-blue-600 hover:text-blue-700"
            >
              Configure agents in Design Blueprint →
            </Link>
          )}
        </div>

        {hasBlueprint && designSession?.blueprint_state?.agents ? (
          <div className="space-y-4">
            {designSession.blueprint_state.agents.map((agent, index) => (
              <div
                key={agent.name || index}
                className="bg-white rounded-lg shadow-sm border border-gray-200 p-5"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                        <svg
                          className="w-5 h-5 text-blue-600"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                          />
                        </svg>
                      </div>
                      <div>
                        <h4 className="font-semibold text-gray-900">{agent.name}</h4>
                        {agent.tone && (
                          <span className="text-xs text-gray-500 capitalize">
                            {agent.tone} tone
                          </span>
                        )}
                      </div>
                    </div>

                    {agent.persona && (
                      <p className="text-sm text-gray-600 mb-3">{agent.persona}</p>
                    )}

                    {agent.topics.length > 0 && (
                      <div className="mb-3">
                        <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                          Topics
                        </span>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {agent.topics.map((topic) => (
                            <span
                              key={topic}
                              className="px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded"
                            >
                              {topic}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="flex gap-2 ml-4">
                    <Link
                      to={`/projects/${projectId}/simulate?designSessionId=${designSession.session_id}&agentIndex=${index}`}
                      className="px-3 py-1.5 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-md"
                    >
                      Simulate
                    </Link>
                    <button
                      onClick={() => {
                        // TODO: Implement assign interviews modal
                        alert(`Assign interviews to "${agent.name}" - Coming soon!`)
                      }}
                      className="px-3 py-1.5 text-sm font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-md border border-blue-200"
                    >
                      Assign Interviews
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-gray-50 rounded-lg border border-gray-200 p-8 text-center">
            <div className="w-12 h-12 bg-gray-200 rounded-full flex items-center justify-center mx-auto mb-3">
              <svg
                className="w-6 h-6 text-gray-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
                />
              </svg>
            </div>
            <p className="text-gray-600 mb-2">No interview agents configured yet</p>
            <p className="text-sm text-gray-500">
              Use the Design Blueprint to create and configure interview agents for this project.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
