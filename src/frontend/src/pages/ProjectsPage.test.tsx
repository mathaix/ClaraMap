import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '../test/utils'
import userEvent from '@testing-library/user-event'
import ProjectsPage from './ProjectsPage'

describe('ProjectsPage', () => {
  beforeEach(() => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })

  it('should render page title and new project button', () => {
    render(<ProjectsPage />)

    expect(screen.getByText('Projects')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /new project/i })).toBeInTheDocument()
  })

  it('should display loading state initially', () => {
    render(<ProjectsPage />)

    expect(screen.getByText(/loading/i)).toBeInTheDocument()
  })

  it('should display projects after loading', async () => {
    render(<ProjectsPage />)

    await waitFor(() => {
      expect(screen.getByText('Discovery Project Alpha')).toBeInTheDocument()
    })

    expect(screen.getByText('Beta Analysis')).toBeInTheDocument()
    expect(screen.getByText('Archived Project')).toBeInTheDocument()
  })

  it('should filter projects by status', async () => {
    const user = userEvent.setup()
    render(<ProjectsPage />)

    await waitFor(() => {
      expect(screen.getByText('Discovery Project Alpha')).toBeInTheDocument()
    })

    await user.selectOptions(screen.getByRole('combobox'), 'active')

    await waitFor(() => {
      expect(screen.getByText('Discovery Project Alpha')).toBeInTheDocument()
      expect(screen.queryByText('Beta Analysis')).not.toBeInTheDocument()
    })
  })

  it('should search projects', async () => {
    const user = userEvent.setup()
    render(<ProjectsPage />)

    await waitFor(() => {
      expect(screen.getByText('Discovery Project Alpha')).toBeInTheDocument()
    })

    await user.type(screen.getByPlaceholderText(/search/i), 'Alpha')

    await waitFor(() => {
      expect(screen.getByText('Discovery Project Alpha')).toBeInTheDocument()
      expect(screen.queryByText('Beta Analysis')).not.toBeInTheDocument()
    })
  })

  it('should open create modal when new project button is clicked', async () => {
    const user = userEvent.setup()
    render(<ProjectsPage />)

    await user.click(screen.getByRole('button', { name: /new project/i }))

    expect(screen.getByText('Create New Project')).toBeInTheDocument()
  })

  it('should show empty state when no projects match filter', async () => {
    const user = userEvent.setup()
    render(<ProjectsPage />)

    await waitFor(() => {
      expect(screen.getByText('Discovery Project Alpha')).toBeInTheDocument()
    })

    await user.type(screen.getByPlaceholderText(/search/i), 'nonexistent-xyz')

    await waitFor(() => {
      expect(screen.getByText(/no projects found/i)).toBeInTheDocument()
    })
  })
})
