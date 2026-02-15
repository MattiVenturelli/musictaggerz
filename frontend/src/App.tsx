import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AppLayout } from '@/components/layout'
import { DashboardPage } from '@/components/dashboard'
import { AlbumListPage, AlbumDetailPage } from '@/components/albums'
import { SettingsPage } from '@/components/settings'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/albums" element={<AlbumListPage />} />
          <Route path="/albums/:id" element={<AlbumDetailPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
