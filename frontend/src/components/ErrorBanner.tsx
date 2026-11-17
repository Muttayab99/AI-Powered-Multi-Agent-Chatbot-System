import { RefreshCwIcon, WifiOffIcon } from 'lucide-react'
import { useHealth } from '@/api/queries'

/** Shown while the gateway can't be reached; disappears by itself once health checks pass again. */
export function ErrorBanner() {
  const health = useHealth()
  if (!health.isError) return null

  return (
    <div role="alert" className="mx-auto mt-3 w-full max-w-3xl px-4 sm:px-6">
      <div className="flex items-center gap-3 rounded-2xl border border-destructive/30 bg-card px-4 py-3 text-sm shadow-sm">
        <WifiOffIcon className="size-4 shrink-0 text-destructive" />
        <span className="flex-1">{health.error.message}</span>
        <button
          type="button"
          onClick={() => void health.refetch()}
          disabled={health.isFetching}
          className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 font-medium hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:opacity-50"
        >
          <RefreshCwIcon className={`size-3.5 ${health.isFetching ? 'animate-spin' : ''}`} /> Retry
        </button>
      </div>
    </div>
  )
}
