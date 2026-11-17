import { MenuIcon } from 'lucide-react'
import { useState } from 'react'
import { useTheme } from '@/lib/theme'
import { Composer } from './Composer'
import { ErrorBanner } from './ErrorBanner'
import { MessageList } from './MessageList'
import { Sidebar } from './Sidebar'
import { Sheet, SheetContent, SheetDescription, SheetTitle } from './ui/sheet'
import { Toaster } from './ui/sonner'

export function AppShell() {
  const theme = useTheme()
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="flex h-dvh overflow-hidden">
      <div className="app-backdrop" aria-hidden />

      {/* Desktop: a floating glass sidebar. Below md it moves into a slide-over sheet. */}
      <aside className="glass m-3 mr-0 hidden w-72 shrink-0 rounded-3xl md:block" aria-label="Chat tools">
        <Sidebar theme={theme} />
      </aside>

      <main className="relative flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-2 px-3 pt-3 md:hidden">
          <button
            type="button"
            onClick={() => setMenuOpen(true)}
            aria-label="Open chat tools"
            className="glass grid size-10 place-items-center rounded-xl focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <MenuIcon className="size-5" />
          </button>
          <span className="font-semibold tracking-tight">Multi-Agent Chat</span>
        </header>

        <ErrorBanner />
        <MessageList />

        <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-background via-background/70 to-transparent px-3 pt-10 pb-3 sm:px-6 sm:pb-5">
          <div className="pointer-events-auto mx-auto w-full max-w-3xl">
            <Composer />
            <p className="mt-2 hidden text-center text-xs text-muted-foreground sm:block">
              Enter to send · Shift+Enter for a new line · / to focus
            </p>
          </div>
        </div>
      </main>

      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent side="left" className="glass w-80 border-r-0 p-0">
          <SheetTitle className="sr-only">Chat tools</SheetTitle>
          <SheetDescription className="sr-only">New chat, loaded context, upload and settings</SheetDescription>
          <Sidebar theme={theme} />
        </SheetContent>
      </Sheet>

      <Toaster theme={theme.resolved} position="top-center" />
    </div>
  )
}
