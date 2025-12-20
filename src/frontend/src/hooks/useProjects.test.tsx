import { describe, it, expect } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactNode } from 'react'
import {
  useProjects,
  useProject,
  useCreateProject,
  useUpdateProject,
  useArchiveProject,
  useDeleteProject,
  useDuplicateProject,
} from './useProjects'
import { mockProjects } from '../test/mocks/handlers'

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
  }
}

describe('useProjects', () => {
  it('should fetch projects list', async () => {
    const { result } = renderHook(() => useProjects(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.items).toHaveLength(mockProjects.length)
  })

  it('should filter by status', async () => {
    const { result } = renderHook(() => useProjects({ status: 'draft' }), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.items).toHaveLength(1)
    expect(result.current.data?.items[0].status).toBe('draft')
  })
})

describe('useProject', () => {
  it('should fetch a single project', async () => {
    const { result } = renderHook(() => useProject('proj_001'), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.id).toBe('proj_001')
    expect(result.current.data?.name).toBe('Discovery Project Alpha')
  })

  it('should not fetch when id is empty', async () => {
    const { result } = renderHook(() => useProject(''), {
      wrapper: createWrapper(),
    })

    expect(result.current.fetchStatus).toBe('idle')
  })
})

describe('useCreateProject', () => {
  it('should create a project', async () => {
    const { result } = renderHook(() => useCreateProject(), {
      wrapper: createWrapper(),
    })

    result.current.mutate({
      name: 'New Test Project',
      description: 'Test description',
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.name).toBe('New Test Project')
    expect(result.current.data?.status).toBe('draft')
  })
})

describe('useUpdateProject', () => {
  it('should update a project', async () => {
    const { result } = renderHook(() => useUpdateProject(), {
      wrapper: createWrapper(),
    })

    result.current.mutate({
      id: 'proj_001',
      data: { name: 'Updated Project Name' },
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.name).toBe('Updated Project Name')
  })
})

describe('useArchiveProject', () => {
  it('should archive a project', async () => {
    const { result } = renderHook(() => useArchiveProject(), {
      wrapper: createWrapper(),
    })

    result.current.mutate('proj_001')

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.status).toBe('archived')
  })
})

describe('useDeleteProject', () => {
  it('should delete a project', async () => {
    const { result } = renderHook(() => useDeleteProject(), {
      wrapper: createWrapper(),
    })

    result.current.mutate('proj_001')

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
  })
})

describe('useDuplicateProject', () => {
  it('should duplicate a project', async () => {
    const { result } = renderHook(() => useDuplicateProject(), {
      wrapper: createWrapper(),
    })

    result.current.mutate('proj_001')

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.name).toContain('(Copy)')
    expect(result.current.data?.status).toBe('draft')
  })
})
