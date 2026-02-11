import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import axios from 'axios'
import { useAuthStore } from '@/stores/authStore'

// ── Validation schema ───────────────────────────────────────────────────────

const loginSchema = z.object({
  username: z.string().min(3),
  password: z.string().min(8),
})

type LoginFormData = z.infer<typeof loginSchema>

// ── Component ───────────────────────────────────────────────────────────────

export function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const login = useAuthStore((s) => s.login)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const isLoading = useAuthStore((s) => s.isLoading)

  const [apiError, setApiError] = useState<string | null>(null)

  // Redirect already-authenticated users to dashboard
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/', { replace: true })
    }
  }, [isAuthenticated, navigate])

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: { username: '', password: '' },
  })

  const onSubmit = async (data: LoginFormData) => {
    setApiError(null)
    try {
      await login(data.username, data.password)
      // navigate is handled by the useEffect above once isAuthenticated flips
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const status = error.response?.status
        if (status === 429) {
          setApiError(t('auth.rateLimited', { minutes: 5 }))
        } else if (status === 401) {
          setApiError(t('auth.loginError'))
        } else {
          setApiError(t('auth.loginError'))
        }
      } else {
        setApiError(t('auth.loginError'))
      }
    }
  }

  // Don't render form if already authenticated (redirecting)
  if (isAuthenticated) {
    return null
  }

  return (
    <div
      className="flex min-h-screen items-center justify-center"
      style={{
        background: 'radial-gradient(ellipse at 20% 50%, rgba(124,58,237,0.12) 0%, transparent 50%), radial-gradient(ellipse at 80% 50%, rgba(6,182,212,0.10) 0%, transparent 50%), #0B0F17',
      }}
    >
      <div className="w-full max-w-sm rounded-lg border border-border bg-card p-8 shadow-sm backdrop-blur-[14px] shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
        <h1 className="mb-6 text-center text-2xl font-bold text-card-foreground">
          {t('auth.loginTitle')}
        </h1>

        {apiError && (
          <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {apiError}
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {/* Username */}
          <div>
            <label
              htmlFor="username"
              className="mb-1 block text-sm font-medium text-card-foreground"
            >
              {t('auth.username')}
            </label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              autoFocus
              {...register('username')}
              className={`w-full rounded-xl border px-3 py-2 text-sm outline-none transition-colors
                bg-background text-foreground placeholder:text-muted-foreground
                focus:ring-2 focus:ring-primary/50 focus:border-primary
                ${errors.username ? 'border-red-500' : 'border-border'}`}
              placeholder={t('auth.username')}
            />
            {errors.username && (
              <p className="mt-1 text-xs text-red-500">
                {errors.username.message}
              </p>
            )}
          </div>

          {/* Password */}
          <div>
            <label
              htmlFor="password"
              className="mb-1 block text-sm font-medium text-card-foreground"
            >
              {t('auth.password')}
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              {...register('password')}
              className={`w-full rounded-xl border px-3 py-2 text-sm outline-none transition-colors
                bg-background text-foreground placeholder:text-muted-foreground
                focus:ring-2 focus:ring-primary/50 focus:border-primary
                ${errors.password ? 'border-red-500' : 'border-border'}`}
              placeholder={t('auth.password')}
            />
            {errors.password && (
              <p className="mt-1 text-xs text-red-500">
                {errors.password.message}
              </p>
            )}
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={isLoading}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading && (
              <svg
                className="h-4 w-4 animate-spin"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
            )}
            {t('auth.login')}
          </button>
        </form>
      </div>
    </div>
  )
}
