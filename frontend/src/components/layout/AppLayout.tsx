import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'

const bgGradient = [
  'radial-gradient(900px circle at 10% 10%, rgba(124,108,255,0.20), transparent 55%)',
  'radial-gradient(800px circle at 90% 20%, rgba(77,225,255,0.12), transparent 55%)',
  'radial-gradient(900px circle at 50% 95%, rgba(255,77,148,0.08), transparent 60%)',
  '#0B0F17',
].join(', ')

export function AppLayout() {
  return (
    <div
      className="flex h-screen overflow-hidden"
      style={{ background: bgGradient }}
    >
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
