import { Moon, Sun } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { useI18n } from '@/i18n/I18nContext'
import { nextTheme, setTheme, useTheme } from '@/lib/theme'

/** Switches between the light and dark look; the choice is remembered on this device. */
export function ThemeToggle({ className }: { className?: string }) {
  const theme = useTheme()
  const { t } = useI18n()
  const label = theme === 'light' ? t('theme.toDark') : t('theme.toLight')
  return (
    <Button variant="ghost" icon className={className} aria-label={label} title={label} onClick={() => setTheme(nextTheme(theme))}>
      {theme === 'light' ? <Moon size={18} aria-hidden /> : <Sun size={18} aria-hidden />}
    </Button>
  )
}
