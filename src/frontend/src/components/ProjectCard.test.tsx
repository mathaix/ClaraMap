import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '../test/utils'
import userEvent from '@testing-library/user-event'
import { ProjectCard } from './ProjectCard'
import type { Project } from '../types/project'

const mockProject: Project = {
  id: 'proj_test',
  name: 'Test Project',
  description: 'A test project description',
  status: 'active',
  timeline_start: '2024-01-01T00:00:00Z',
  timeline_end: '2024-06-30T00:00:00Z',
  tags: ['discovery', 'test'],
  created_at: '2024-01-01T10:00:00Z',
  updated_at: '2024-01-15T14:30:00Z',
  created_by: 'user_001',
}

describe('ProjectCard', () => {
  it('should render project name and description', () => {
    render(<ProjectCard project={mockProject} />)

    expect(screen.getByText('Test Project')).toBeInTheDocument()
    expect(screen.getByText('A test project description')).toBeInTheDocument()
  })

  it('should render status badge', () => {
    render(<ProjectCard project={mockProject} />)

    expect(screen.getByText('active')).toBeInTheDocument()
  })

  it('should render tags', () => {
    render(<ProjectCard project={mockProject} />)

    expect(screen.getByText('discovery')).toBeInTheDocument()
    expect(screen.getByText('test')).toBeInTheDocument()
  })

  it('should link to project detail page', () => {
    render(<ProjectCard project={mockProject} />)

    const link = screen.getByRole('link', { name: 'Test Project' })
    expect(link).toHaveAttribute('href', '/projects/proj_test')
  })

  it('should call onArchive when archive button is clicked', async () => {
    const user = userEvent.setup()
    const onArchive = vi.fn()

    render(<ProjectCard project={mockProject} onArchive={onArchive} />)

    await user.click(screen.getByTitle('Archive'))
    expect(onArchive).toHaveBeenCalledWith('proj_test')
  })

  it('should call onDelete when delete button is clicked', async () => {
    const user = userEvent.setup()
    const onDelete = vi.fn()

    render(<ProjectCard project={mockProject} onDelete={onDelete} />)

    await user.click(screen.getByTitle('Delete'))
    expect(onDelete).toHaveBeenCalledWith('proj_test')
  })

  it('should call onDuplicate when duplicate button is clicked', async () => {
    const user = userEvent.setup()
    const onDuplicate = vi.fn()

    render(<ProjectCard project={mockProject} onDuplicate={onDuplicate} />)

    await user.click(screen.getByTitle('Duplicate'))
    expect(onDuplicate).toHaveBeenCalledWith('proj_test')
  })

  it('should not show archive button for archived projects', () => {
    const archivedProject: Project = {
      ...mockProject,
      status: 'archived',
    }

    render(<ProjectCard project={archivedProject} onArchive={vi.fn()} />)

    expect(screen.queryByTitle('Archive')).not.toBeInTheDocument()
  })

  it('should render correctly with no tags', () => {
    const projectWithoutTags: Project = {
      ...mockProject,
      tags: [],
    }

    render(<ProjectCard project={projectWithoutTags} />)

    expect(screen.getByText('Test Project')).toBeInTheDocument()
  })

  it('should display different status styles', () => {
    const draftProject: Project = { ...mockProject, status: 'draft' }
    const { rerender } = render(<ProjectCard project={draftProject} />)
    expect(screen.getByText('draft')).toBeInTheDocument()

    const completedProject: Project = { ...mockProject, status: 'completed' }
    rerender(<ProjectCard project={completedProject} />)
    expect(screen.getByText('completed')).toBeInTheDocument()
  })
})
