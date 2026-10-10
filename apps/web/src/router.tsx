import { Suspense, lazy, type ComponentType } from 'react'
import { createBrowserRouter, type RouteObject } from 'react-router-dom'
import { LoadingState } from '@/components/common/LoadingState'
import { RoutePlaceholder } from '@/components/common/RoutePlaceholder'
import { AppLayout, Home } from '@/pages/AppLayout'
import CameraCheck from '@/pages/dev/CameraCheck'
import ComponentsPreview from '@/pages/dev/ComponentsPreview'
import { LoginScreen } from '@/pages/login/LoginScreen'
import { NotFound, RequireRole } from '@/pages/RequireRole'
import { ROUTES } from './routes'

/**
 * The real screens, loaded on demand. A path that is not listed here still shows its placeholder.
 * Plans A2 to A9 add one line per finished screen.
 */
const SCREENS: Record<string, ComponentType> = {
  'store/receive': lazy(() => import('@/pages/store/ReceiveYarn')),
  'store/stock': lazy(() => import('@/pages/store/YarnStock')),
  orders: lazy(() => import('@/pages/orders/OrdersList')),
  'orders/new': lazy(() => import('@/pages/orders/NewOrder')),
  'orders/:code': lazy(() => import('@/pages/orders/OrderDetail')),
}

/** All routes. Exported separately so tests can mount them in a memory router. */
export const routeObjects: RouteObject[] = [
  { path: '/login', element: <LoginScreen /> },
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <Home /> },
      ...ROUTES.map((r) => {
        const Screen = SCREENS[r.path]
        return {
          path: r.path,
          element: (
            <RequireRole roles={r.roles}>
              {Screen ? (
                <Suspense fallback={<LoadingState />}>
                  <Screen />
                </Suspense>
              ) : (
                <RoutePlaceholder title={r.title} description={r.description} />
              )}
            </RequireRole>
          ),
        }
      }),
      { path: 'dev/camera', element: <CameraCheck /> },
      { path: 'dev/components', element: <ComponentsPreview /> },
      { path: '*', element: <NotFound /> },
    ],
  },
]

export const router = createBrowserRouter(routeObjects)
