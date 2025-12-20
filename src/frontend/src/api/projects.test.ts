import { describe, it, expect } from 'vitest'
import { projectsApi } from './projects'
import { mockProjects } from '../test/mocks/handlers'

describe('projectsApi', () => {
  describe('list', () => {
    it('should fetch all projects', async () => {
      const result = await projectsApi.list()

      expect(result.items).toHaveLength(mockProjects.length)
      expect(result.total).toBe(mockProjects.length)
    })

    it('should filter projects by status', async () => {
      const result = await projectsApi.list({ status: 'active' })

      expect(result.items).toHaveLength(1)
      expect(result.items[0].status).toBe('active')
    })

    it('should search projects by name', async () => {
      const result = await projectsApi.list({ search: 'Alpha' })

      expect(result.items).toHaveLength(1)
      expect(result.items[0].name).toContain('Alpha')
    })

    it('should search projects by description', async () => {
      const result = await projectsApi.list({ search: 'stakeholder' })

      expect(result.items).toHaveLength(1)
      expect(result.items[0].description).toContain('stakeholder')
    })
  })

  describe('get', () => {
    it('should fetch a single project by id', async () => {
      const result = await projectsApi.get('proj_001')

      expect(result.id).toBe('proj_001')
      expect(result.name).toBe('Discovery Project Alpha')
    })

    it('should throw on non-existent project', async () => {
      await expect(projectsApi.get('nonexistent')).rejects.toThrow()
    })
  })

  describe('create', () => {
    it('should create a new project', async () => {
      const result = await projectsApi.create({
        name: 'New Project',
        description: 'A new test project',
        tags: ['test'],
      })

      expect(result.id).toBeDefined()
      expect(result.name).toBe('New Project')
      expect(result.description).toBe('A new test project')
      expect(result.status).toBe('draft')
      expect(result.tags).toContain('test')
    })
  })

  describe('update', () => {
    it('should update an existing project', async () => {
      const result = await projectsApi.update('proj_001', {
        name: 'Updated Name',
      })

      expect(result.id).toBe('proj_001')
      expect(result.name).toBe('Updated Name')
    })

    it('should throw on non-existent project', async () => {
      await expect(
        projectsApi.update('nonexistent', { name: 'Test' })
      ).rejects.toThrow()
    })
  })

  describe('archive', () => {
    it('should archive a project', async () => {
      const result = await projectsApi.archive('proj_001')

      expect(result.id).toBe('proj_001')
      expect(result.status).toBe('archived')
    })
  })

  describe('delete', () => {
    it('should delete a project', async () => {
      await expect(projectsApi.delete('proj_001')).resolves.toBeUndefined()
    })

    it('should throw on non-existent project', async () => {
      await expect(projectsApi.delete('nonexistent')).rejects.toThrow()
    })
  })

  describe('duplicate', () => {
    it('should duplicate a project', async () => {
      const result = await projectsApi.duplicate('proj_001')

      expect(result.id).not.toBe('proj_001')
      expect(result.name).toBe('Discovery Project Alpha (Copy)')
      expect(result.status).toBe('draft')
    })
  })
})
