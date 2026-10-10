import { Moon, Sun } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { nextTheme, setTheme, useTheme } from '@/lib/theme'

/** Switches between the light and dark look; the choice is remembered on this device. */
export function ThemeToggle({ className }: { className?: string }) {
  const theme = useTheme()
  const label = theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'
  return (
    <Button variant="ghost" icon className={className} aria-label={label} title={label} onClick={() => setTheme(nextTheme(theme))}>
      {theme === 'light' ? <Moon size={18} aria-hidden /> : <Sun size={18} aria-hidden />}
    </Button>
  )
}
