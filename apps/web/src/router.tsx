import { Suspense, lazy, type ComponentType } from 'react'
import { createBrowserRouter, type RouteObject } from 'react-router-dom'
import { LoadingState } from '@/components/common/LoadingState'
import { RoutePlaceholder } from '@/components/common/RoutePlaceholder'
import { AppLayout } from '@/pages/AppLayout'
import CameraCheck from '@/pages/dev/CameraCheck'
import ComponentsPreview from '@/pages/dev/ComponentsPreview'
import { LandingGate } from '@/pages/landing/LandingPage'
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
  'store/lots/:code': lazy(() => import('@/pages/store/LotDetail')),
  'r/:code': lazy(() => import('@/pages/rolls/RollPassport')),
  'invoices/:no': lazy(() => import('@/pages/money/InvoicePage')),
  'money/receivables': lazy(() => import('@/pages/money/Receivables')),
  'money/payables': lazy(() => import('@/pages/money/Payables')),
  'admin/suppliers': lazy(() => import('@/pages/admin/screens').then((m) => ({ default: m.Suppliers }))),
  'admin/buyers': lazy(() => import('@/pages/admin/screens').then((m) => ({ default: m.Buyers }))),
  'admin/yarn-types': lazy(() => import('@/pages/admin/screens').then((m) => ({ default: m.YarnTypes }))),
  'admin/fabric-types': lazy(() => import('@/pages/admin/FabricTypes')),
  'admin/machines': lazy(() => import('@/pages/admin/screens').then((m) => ({ default: m.Machines }))),
  'admin/shifts': lazy(() => import('@/pages/admin/screens').then((m) => ({ default: m.Shifts }))),
  'admin/users': lazy(() => import('@/pages/admin/screens').then((m) => ({ default: m.Users }))),
  'people/workers': lazy(() => import('@/pages/admin/screens').then((m) => ({ default: m.Workers }))),
  owner: lazy(() => import('@/pages/owner/OwnerDashboard')),
  'owner/insights': lazy(() => import('@/pages/owner/Insights')),
  'people/attendance': lazy(() => import('@/pages/people/Attendance')),
  'people/wages': lazy(() => import('@/pages/people/Wages')),
  copilot: lazy(() => import('@/pages/ai/Copilot')),
  'settings/ai': lazy(() => import('@/pages/ai/AiSettings')),
  'settings/ai/report-card': lazy(() => import('@/pages/ai/ReportCard')),
  dispatch: lazy(() => import('@/pages/dispatch/DispatchList')),
  'dispatch/:code': lazy(() => import('@/pages/dispatch/DispatchDetail')),
  qc: lazy(() => import('@/pages/qc/QcQueue')),
  'qc/model': lazy(() => import('@/pages/qc/ModelCard')),
  'qc/:rollCode': lazy(() => import('@/pages/qc/QcInspect')),
  floor: lazy(() => import('@/pages/floor/FloorBoard')),
  'floor/machines/:code': lazy(() => import('@/pages/floor/MachineDetail')),
  orders: lazy(() => import('@/pages/orders/OrdersList')),
  'orders/new': lazy(() => import('@/pages/orders/NewOrder')),
  'orders/:code': lazy(() => import('@/pages/orders/OrderDetail')),
}

/** All routes. Exported separately so tests can mount them in a memory router. */
export const routeObjects: RouteObject[] = [
  { path: '/', element: <LandingGate /> },
  { path: '/login', element: <LoginScreen /> },
  {
    element: <AppLayout />,
    children: [
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
      // developer pages: owner only, so no other login can wander in by typing the address
      { path: 'dev/camera', element: <RequireRole roles={['owner']}><CameraCheck /></RequireRole> },
      { path: 'dev/components', element: <RequireRole roles={['owner']}><ComponentsPreview /></RequireRole> },
      { path: '*', element: <NotFound /> },
    ],
  },
]

export const router = createBrowserRouter(routeObjects)
