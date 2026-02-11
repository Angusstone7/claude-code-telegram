import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useUsers, useCreateUser, useResetPassword } from '@/hooks/useAuth'
import { UserPlus, KeyRound, X, Loader2, AlertCircle } from 'lucide-react'
import type { UserProfile } from '@/types/api'
import { isAxiosError } from 'axios'

// ── Create User Modal ────────────────────────────────────────────────────────

interface CreateUserFormState {
  username: string
  password: string
  display_name: string
  telegram_id: string
}

const emptyForm: CreateUserFormState = {
  username: '',
  password: '',
  display_name: '',
  telegram_id: '',
}

function CreateUserModal({
  onClose,
}: {
  onClose: () => void
}) {
  const { t } = useTranslation()
  const createUser = useCreateUser()
  const [form, setForm] = useState<CreateUserFormState>(emptyForm)
  const [error, setError] = useState<string | null>(null)

  const handleChange = (field: keyof CreateUserFormState, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }))
    setError(null)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    const payload = {
      username: form.username.trim(),
      password: form.password,
      display_name: form.display_name.trim() || form.username.trim(),
      ...(form.telegram_id.trim()
        ? { telegram_id: Number(form.telegram_id.trim()) }
        : {}),
    }

    createUser.mutate(payload, {
      onSuccess: () => onClose(),
      onError: (err) => {
        if (isAxiosError(err) && err.response?.status === 409) {
          const detail = err.response.data?.detail
          setError(typeof detail === 'string' ? detail : 'Username or Telegram ID already exists')
        } else {
          setError(t('common.error'))
        }
      },
    })
  }

  const isValid = form.username.trim().length > 0 && form.password.length >= 4

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg border border-gray-700 bg-gray-800 p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-100">{t('users.createUser')}</h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-gray-700 hover:text-gray-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-md bg-red-900/50 px-3 py-2 text-sm text-red-300">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-300">
              {t('auth.username')} *
            </label>
            <input
              type="text"
              value={form.username}
              onChange={(e) => handleChange('username', e.target.value)}
              className="w-full rounded-md border border-gray-600 bg-gray-700 px-3 py-2 text-gray-100 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              autoFocus
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-300">
              {t('auth.password')} *
            </label>
            <input
              type="password"
              value={form.password}
              onChange={(e) => handleChange('password', e.target.value)}
              className="w-full rounded-md border border-gray-600 bg-gray-700 px-3 py-2 text-gray-100 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-300">
              {t('settings.displayName')}
            </label>
            <input
              type="text"
              value={form.display_name}
              onChange={(e) => handleChange('display_name', e.target.value)}
              className="w-full rounded-md border border-gray-600 bg-gray-700 px-3 py-2 text-gray-100 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-300">
              {t('settings.telegramId')}
            </label>
            <input
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              value={form.telegram_id}
              onChange={(e) => handleChange('telegram_id', e.target.value)}
              className="w-full rounded-md border border-gray-600 bg-gray-700 px-3 py-2 text-gray-100 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-gray-600 px-4 py-2 text-sm font-medium text-gray-300 hover:bg-gray-700"
            >
              {t('common.cancel')}
            </button>
            <button
              type="submit"
              disabled={!isValid || createUser.isPending}
              className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {createUser.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              {t('common.save')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Reset Password Dialog ────────────────────────────────────────────────────

function ResetPasswordDialog({
  user,
  onClose,
}: {
  user: UserProfile
  onClose: () => void
}) {
  const { t } = useTranslation()
  const resetPassword = useResetPassword()
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    resetPassword.mutate(
      { userId: user.id, newPassword: password },
      {
        onSuccess: () => onClose(),
        onError: () => setError(t('common.error')),
      },
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-sm rounded-lg border border-gray-700 bg-gray-800 p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-100">{t('users.resetPassword')}</h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-gray-700 hover:text-gray-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <p className="mb-4 text-sm text-gray-400">
          {user.username} ({user.display_name})
        </p>

        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-md bg-red-900/50 px-3 py-2 text-sm text-red-300">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-300">
              {t('auth.password')} *
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value)
                setError(null)
              }}
              className="w-full rounded-md border border-gray-600 bg-gray-700 px-3 py-2 text-gray-100 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              autoFocus
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-gray-600 px-4 py-2 text-sm font-medium text-gray-300 hover:bg-gray-700"
            >
              {t('common.cancel')}
            </button>
            <button
              type="submit"
              disabled={password.length < 4 || resetPassword.isPending}
              className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {resetPassword.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              {t('common.save')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Users Page ───────────────────────────────────────────────────────────────

export function UsersPage() {
  const { t } = useTranslation()
  const { data: users, isLoading, error } = useUsers()
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [resetPasswordUser, setResetPasswordUser] = useState<UserProfile | null>(null)

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-'
    return new Date(dateStr).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-100">{t('users.title')}</h1>
        <button
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <UserPlus className="h-4 w-4" />
          {t('users.createUser')}
        </button>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
          <span className="ml-3 text-gray-400">{t('common.loading')}</span>
        </div>
      )}

      {/* Error state */}
      {error && !isLoading && (
        <div className="flex items-center gap-2 rounded-md bg-red-900/50 px-4 py-3 text-red-300">
          <AlertCircle className="h-5 w-5 shrink-0" />
          {t('common.error')}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !error && users && users.length === 0 && (
        <div className="py-12 text-center text-gray-400">{t('common.noData')}</div>
      )}

      {/* Users table */}
      {!isLoading && !error && users && users.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-gray-700">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-gray-700 bg-gray-800/50 text-xs uppercase text-gray-400">
              <tr>
                <th className="px-4 py-3">ID</th>
                <th className="px-4 py-3">{t('auth.username')}</th>
                <th className="px-4 py-3">{t('settings.displayName')}</th>
                <th className="px-4 py-3">{t('settings.telegramId')}</th>
                <th className="px-4 py-3">{t('users.role')}</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3">{t('common.actions')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {users.map((user) => (
                <tr key={user.id} className="bg-gray-800 hover:bg-gray-750">
                  <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-gray-400">
                    {user.id.slice(0, 8)}...
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 font-medium text-gray-100">
                    {user.username}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-gray-300">
                    {user.display_name}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 font-mono text-gray-300">
                    {user.telegram_id ?? '-'}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        user.role === 'admin'
                          ? 'bg-purple-900/50 text-purple-300'
                          : user.role === 'operator'
                            ? 'bg-blue-900/50 text-blue-300'
                            : 'bg-gray-700 text-gray-300'
                      }`}
                    >
                      {user.role}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-gray-400">
                    {formatDate(user.created_at)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <button
                      onClick={() => setResetPasswordUser(user)}
                      className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium text-gray-300 hover:bg-gray-700 hover:text-gray-100"
                      title={t('users.resetPassword')}
                    >
                      <KeyRound className="h-3.5 w-3.5" />
                      {t('users.resetPassword')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create User Modal */}
      {showCreateModal && (
        <CreateUserModal onClose={() => setShowCreateModal(false)} />
      )}

      {/* Reset Password Dialog */}
      {resetPasswordUser && (
        <ResetPasswordDialog
          user={resetPasswordUser}
          onClose={() => setResetPasswordUser(null)}
        />
      )}
    </div>
  )
}
