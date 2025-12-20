import { Link } from 'react-router-dom'
import { format } from 'date-fns'
import clsx from 'clsx'
import type { Project, ProjectStatus } from '../types/project'

interface ProjectCardProps {
  project: Project
  onArchive?: (id: string) => void
  onDelete?: (id: string) => void
  onDuplicate?: (id: string) => void
}

const statusStyles: Record<ProjectStatus, string> = {
  draft: 'bg-gray-100 text-gray-700',
  active: 'bg-green-100 text-green-700',
  completed: 'bg-blue-100 text-blue-700',
  archived: 'bg-yellow-100 text-yellow-700',
}

export function ProjectCard({
  project,
  onArchive,
  onDelete,
  onDuplicate,
}: ProjectCardProps) {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <Link
            to={`/projects/${project.id}`}
            className="text-lg font-medium text-gray-900 hover:text-blue-600 truncate block"
          >
            {project.name}
          </Link>
          <p className="mt-1 text-sm text-gray-500 line-clamp-2">
            {project.description}
          </p>
        </div>
        <span
          className={clsx(
            'ml-4 px-2.5 py-0.5 rounded-full text-xs font-medium capitalize',
            statusStyles[project.status]
          )}
        >
          {project.status}
        </span>
      </div>

      {project.tags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
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

      <div className="mt-4 flex items-center justify-between text-sm text-gray-500">
        <span>Updated {format(new Date(project.updated_at), 'MMM d, yyyy')}</span>
        <div className="flex gap-2">
          {onDuplicate && (
            <button
              onClick={() => onDuplicate(project.id)}
              className="text-gray-400 hover:text-gray-600"
              title="Duplicate"
            >
              Duplicate
            </button>
          )}
          {project.status !== 'archived' && onArchive && (
            <button
              onClick={() => onArchive(project.id)}
              className="text-gray-400 hover:text-yellow-600"
              title="Archive"
            >
              Archive
            </button>
          )}
          {onDelete && (
            <button
              onClick={() => onDelete(project.id)}
              className="text-gray-400 hover:text-red-600"
              title="Delete"
            >
              Delete
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
