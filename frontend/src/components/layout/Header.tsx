import { useTranslation } from 'react-i18next'
import { LogOut, User } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'

export function Header() {
  const { t, i18n } = useTranslation()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)

  const handleLanguageChange = (lang: string) => {
    i18n.changeLanguage(lang)
    localStorage.setItem('language', lang)
  }

  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-background px-6">
      <div />
      <div className="flex items-center gap-4">
        <select
          value={i18n.language}
          onChange={(e) => handleLanguageChange(e.target.value)}
          className="rounded-md border border-input bg-background px-2 py-1 text-sm"
        >
          <option value="ru">RU</option>
          <option value="en">EN</option>
          <option value="zh">ZH</option>
        </select>
        {user && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <User className="h-4 w-4" />
            <span>{user.display_name}</span>
          </div>
        )}
        <button
          onClick={() => logout()}
          className="flex items-center gap-1 rounded-md px-2 py-1 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
          title={t('auth.logout')}
        >
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </header>
  )
}
