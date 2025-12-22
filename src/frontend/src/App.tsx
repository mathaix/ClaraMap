import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import ProjectsPage from './pages/ProjectsPage'
import ProjectDetailPage from './pages/ProjectDetailPage'
import { DesignAssistantPage } from './pages/DesignAssistantPage'
import { SimulationPage } from './pages/SimulationPage'
import { AutomatedSimulationPage } from './pages/AutomatedSimulationPage'

function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <h1 className="text-xl font-semibold text-gray-900">Clara</h1>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  )
}

function App() {
  const location = useLocation()
  const isFullScreenPage = location.pathname.includes('/design') || location.pathname.includes('/simulate') || location.pathname.includes('/auto-simulate')

  // Design Assistant and Simulation pages use full-screen layout
  if (isFullScreenPage) {
    return (
      <Routes>
        <Route path="/projects/:projectId/design" element={<DesignAssistantPage />} />
        <Route path="/projects/:projectId/simulate" element={<SimulationPage />} />
        <Route path="/projects/:projectId/auto-simulate" element={<AutomatedSimulationPage />} />
      </Routes>
    )
  }

  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<Navigate to="/projects" replace />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
      </Routes>
    </AppLayout>
  )
}

export default App
