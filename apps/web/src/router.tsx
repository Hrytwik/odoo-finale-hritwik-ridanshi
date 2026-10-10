import { createBrowserRouter, type RouteObject } from 'react-router-dom'
import { RoutePlaceholder } from '@/components/common/RoutePlaceholder'
import { AppLayout, Home } from '@/pages/AppLayout'
import CameraCheck from '@/pages/dev/CameraCheck'
import ComponentsPreview from '@/pages/dev/ComponentsPreview'
import { LoginScreen } from '@/pages/login/LoginScreen'
import { NotFound, RequireRole } from '@/pages/RequireRole'
import { ROUTES } from './routes'

/** All routes. Exported separately so tests can mount them in a memory router. */
export const routeObjects: RouteObject[] = [
  { path: '/login', element: <LoginScreen /> },
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <Home /> },
      ...ROUTES.map((r) => ({
        path: r.path,
        element: (
          <RequireRole roles={r.roles}>
            <RoutePlaceholder title={r.title} description={r.description} />
          </RequireRole>
        ),
      })),
      { path: 'dev/camera', element: <CameraCheck /> },
      { path: 'dev/components', element: <ComponentsPreview /> },
      { path: '*', element: <NotFound /> },
    ],
  },
]

export const router = createBrowserRouter(routeObjects)
