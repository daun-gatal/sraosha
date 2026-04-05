import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/layout/AppLayout'
import { ContractsPage } from './pages/ContractsPage'
import { ContractEditorPage } from './pages/contracts/ContractEditorPage'
import { DataQualityPage } from './pages/DataQualityPage'
import { DataQualityEditorPage } from './pages/data-quality/DataQualityEditorPage'
import { HomePage } from './pages/HomePage'
import { RunsPage } from './pages/RunsPage'
import { SchedulesPage } from './pages/SchedulesPage'
import { AlertingSettingsPage } from './pages/settings/AlertingSettingsPage'
import { ConnectionsSettingsPage } from './pages/settings/ConnectionsSettingsPage'
import { SettingsLayout } from './pages/settings/SettingsLayout'
import { TeamsSettingsPage } from './pages/settings/TeamsSettingsPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
})

/** Match Vite `base` (dev `/`, prod `/app/`). See `vite.config.ts`. */
function routerBasename(): string | undefined {
  const trimmed = import.meta.env.BASE_URL.replace(/\/$/, '')
  return trimmed || undefined
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename={routerBasename()}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<HomePage />} />
            <Route path="contracts" element={<Outlet />}>
              <Route index element={<ContractsPage />} />
              <Route path="new" element={<ContractEditorPage />} />
              <Route path=":contractId" element={<ContractEditorPage />} />
            </Route>
            <Route path="runs" element={<RunsPage />} />
            <Route path="data-quality" element={<Outlet />}>
              <Route index element={<DataQualityPage />} />
              <Route path="new" element={<DataQualityEditorPage />} />
              <Route path=":checkId" element={<DataQualityEditorPage />} />
            </Route>
            <Route path="schedules" element={<SchedulesPage />} />
            <Route path="settings" element={<SettingsLayout />}>
              <Route index element={<Navigate to="teams" replace />} />
              <Route path="teams" element={<TeamsSettingsPage />} />
              <Route path="alerting" element={<AlertingSettingsPage />} />
              <Route path="connections" element={<ConnectionsSettingsPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
