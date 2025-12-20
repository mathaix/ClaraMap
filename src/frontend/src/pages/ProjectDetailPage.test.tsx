import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import ProjectDetailPage from './ProjectDetailPage'

function renderWithRoute(projectId: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/projects/${projectId}`]}>
        <Routes>
          <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
          <Route path="/projects" element={<div>Projects List</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('ProjectDetailPage', () => {
  beforeEach(() => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })

  it('should display loading state initially', () => {
    renderWithRoute('proj_001')

    expect(screen.getByText(/loading/i)).toBeInTheDocument()
  })

  it('should display project details after loading', async () => {
    renderWithRoute('proj_001')

    await waitFor(() => {
      expect(screen.getByText('Discovery Project Alpha')).toBeInTheDocument()
    })

    expect(screen.getByText('active')).toBeInTheDocument()
    expect(screen.getByText(/first discovery project/i)).toBeInTheDocument()
    expect(screen.getByText('discovery')).toBeInTheDocument()
    expect(screen.getByText('enterprise')).toBeInTheDocument()
  })

  it('should show back link', async () => {
    renderWithRoute('proj_001')

    await waitFor(() => {
      expect(screen.getByText('Discovery Project Alpha')).toBeInTheDocument()
    })

    expect(screen.getByText(/back to projects/i)).toBeInTheDocument()
  })

  it('should show error for non-existent project', async () => {
    renderWithRoute('nonexistent')

    await waitFor(() => {
      expect(screen.getByText(/failed to load/i)).toBeInTheDocument()
    })
  })

  it('should enter edit mode when edit button is clicked', async () => {
    const user = userEvent.setup()
    renderWithRoute('proj_001')

    await waitFor(() => {
      expect(screen.getByText('Discovery Project Alpha')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /edit/i }))

    expect(screen.getByDisplayValue('Discovery Project Alpha')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument()
  })

  it('should cancel edit mode', async () => {
    const user = userEvent.setup()
    renderWithRoute('proj_001')

    await waitFor(() => {
      expect(screen.getByText('Discovery Project Alpha')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /edit/i }))
    await user.click(screen.getByRole('button', { name: /cancel/i }))

    expect(screen.queryByDisplayValue('Discovery Project Alpha')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument()
  })

  it('should show action buttons', async () => {
    renderWithRoute('proj_001')

    await waitFor(() => {
      expect(screen.getByText('Discovery Project Alpha')).toBeInTheDocument()
    })

    expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /archive/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument()
  })

  it('should not show archive button for archived project', async () => {
    renderWithRoute('proj_003')

    await waitFor(() => {
      expect(screen.getByText('Archived Project')).toBeInTheDocument()
    })

    expect(screen.queryByRole('button', { name: /archive/i })).not.toBeInTheDocument()
  })
})
