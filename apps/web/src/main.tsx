import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/inter'
import '@fontsource-variable/fraunces'
import './styles/theme.css'
import './styles/base.css'
import './styles/components.css'
import './styles/layout.css'
import './styles/motion.css'
import './styles/textile.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
