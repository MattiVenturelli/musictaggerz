import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { ToastContainer } from '@/components/common'
import { useWebSocket } from '@/hooks'

export function AppLayout() {
  useWebSocket()

  return (
    <div className="min-h-screen bg-surface-300">
      <Sidebar />
      <main className="ml-64 p-6">
        <Outlet />
      </main>
      <ToastContainer />
    </div>
  )
}
