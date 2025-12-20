import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '../test/utils'
import userEvent from '@testing-library/user-event'
import { CreateProjectModal } from './CreateProjectModal'

describe('CreateProjectModal', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    onSubmit: vi.fn(),
  }

  it('should not render when closed', () => {
    render(<CreateProjectModal {...defaultProps} isOpen={false} />)

    expect(screen.queryByText('Create New Project')).not.toBeInTheDocument()
  })

  it('should render when open', () => {
    render(<CreateProjectModal {...defaultProps} />)

    expect(screen.getByText('Create New Project')).toBeInTheDocument()
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/description/i)).toBeInTheDocument()
  })

  it('should call onSubmit with form data', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()

    render(<CreateProjectModal {...defaultProps} onSubmit={onSubmit} />)

    await user.type(screen.getByLabelText(/^name/i), 'New Project')
    await user.type(screen.getByLabelText(/description/i), 'Project description')
    await user.type(screen.getByLabelText(/tags/i), 'tag1, tag2')
    await user.click(screen.getByRole('button', { name: /create project/i }))

    expect(onSubmit).toHaveBeenCalledWith({
      name: 'New Project',
      description: 'Project description',
      tags: ['tag1', 'tag2'],
      timeline_start: undefined,
      timeline_end: undefined,
    })
  })

  it('should call onClose when cancel is clicked', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()

    render(<CreateProjectModal {...defaultProps} onClose={onClose} />)

    await user.click(screen.getByRole('button', { name: /cancel/i }))

    expect(onClose).toHaveBeenCalled()
  })

  it('should disable submit button when name is empty', () => {
    render(<CreateProjectModal {...defaultProps} />)

    const submitButton = screen.getByRole('button', { name: /create project/i })
    expect(submitButton).toBeDisabled()
  })

  it('should disable submit button when description is empty', async () => {
    const user = userEvent.setup()
    render(<CreateProjectModal {...defaultProps} />)

    await user.type(screen.getByLabelText(/^name/i), 'Project Name')

    const submitButton = screen.getByRole('button', { name: /create project/i })
    expect(submitButton).toBeDisabled()
  })

  it('should enable submit button when required fields are filled', async () => {
    const user = userEvent.setup()
    render(<CreateProjectModal {...defaultProps} />)

    await user.type(screen.getByLabelText(/^name/i), 'Project Name')
    await user.type(screen.getByLabelText(/description/i), 'Description')

    const submitButton = screen.getByRole('button', { name: /create project/i })
    expect(submitButton).toBeEnabled()
  })

  it('should show loading state', () => {
    render(<CreateProjectModal {...defaultProps} isLoading />)

    expect(screen.getByRole('button', { name: /creating/i })).toBeInTheDocument()
  })

  it('should handle timeline dates', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()

    render(<CreateProjectModal {...defaultProps} onSubmit={onSubmit} />)

    await user.type(screen.getByLabelText(/^name/i), 'Project')
    await user.type(screen.getByLabelText(/description/i), 'Description')
    await user.type(screen.getByLabelText(/start date/i), '2024-01-01')
    await user.type(screen.getByLabelText(/end date/i), '2024-12-31')
    await user.click(screen.getByRole('button', { name: /create project/i }))

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        timeline_start: '2024-01-01',
        timeline_end: '2024-12-31',
      })
    )
  })

  it('should parse comma-separated tags correctly', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()

    render(<CreateProjectModal {...defaultProps} onSubmit={onSubmit} />)

    await user.type(screen.getByLabelText(/^name/i), 'Project')
    await user.type(screen.getByLabelText(/description/i), 'Description')
    await user.type(screen.getByLabelText(/tags/i), '  tag1 ,  tag2  , tag3  ')
    await user.click(screen.getByRole('button', { name: /create project/i }))

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        tags: ['tag1', 'tag2', 'tag3'],
      })
    )
  })
})
