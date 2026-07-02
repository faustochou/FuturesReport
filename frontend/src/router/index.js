import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Process from '../views/MainView.vue'
import SimulationView from '../views/SimulationView.vue'
import SimulationRunView from '../views/SimulationRunView.vue'
import ReportView from '../views/ReportView.vue'
import InteractionView from '../views/InteractionView.vue'
import AdminView from '../views/AdminView.vue'
import SubscriptionView from '../views/SubscriptionView.vue'
import SimulateLaunchView from '../views/SimulateLaunchView.vue'
import { authState } from '../store/auth'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/subscription',
    name: 'Subscription',
    component: SubscriptionView
  },
  {
    path: '/launch',
    name: 'SimulateLaunch',
    component: SimulateLaunchView,
    meta: { requiresSubscription: true }
  },
  {
    path: '/process/:projectId',
    name: 'Process',
    component: Process,
    props: true
  },
  {
    path: '/simulation/:simulationId',
    name: 'Simulation',
    component: SimulationView,
    props: true
  },
  {
    path: '/simulation/:simulationId/start',
    name: 'SimulationRun',
    component: SimulationRunView,
    props: true
  },
  {
    path: '/report/:reportId',
    name: 'Report',
    component: ReportView,
    props: true
  },
  {
    path: '/interaction/:reportId',
    name: 'Interaction',
    component: InteractionView,
    props: true
  },
  {
    path: '/admin',
    name: 'Admin',
    component: AdminView
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, _from, next) => {
  // Block non-admin users from /admin
  if (to.name === 'Admin') {
    const isAdmin = authState.user?.is_admin
    const hasAdminToken = !!localStorage.getItem('futures_admin_token')
    if (!isAdmin && !hasAdminToken) {
      next({ path: '/' })
      return
    }
  }

  // Pages with requiresSubscription: redirect to /subscription when not subscribed.
  // The SimulateLaunchView also shows its own gate UI for finer-grained feedback,
  // but this guard prevents direct URL access without any subscription at all.
  if (to.meta?.requiresSubscription) {
    if (!authState.token) {
      next({ path: '/' })
      return
    }
    const sub = authState.user?.subscription
    const hasActiveSub = sub?.status === 'active' && ['lite', 'premium', 'pro'].includes(sub?.tier_code)
    if (!hasActiveSub) {
      next({ path: '/subscription' })
      return
    }
  }

  next()
})

export default router
