import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Process from '../views/MainView.vue'
import SimulationView from '../views/SimulationView.vue'
import SimulationRunView from '../views/SimulationRunView.vue'
import ReportView from '../views/ReportView.vue'
import InteractionView from '../views/InteractionView.vue'
import AdminView from '../views/AdminView.vue'
import SubscriptionView from '../views/SubscriptionView.vue'
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

// Block non-admin users from accessing /admin directly.
// authState.user is populated synchronously from localStorage on app init,
// so this check is reliable even on first page load / hard refresh.
router.beforeEach((to, _from, next) => {
  if (to.name === 'Admin') {
    const isAdmin = authState.user?.is_admin
    // Also allow users who already hold a valid admin session token
    const hasAdminToken = !!localStorage.getItem('futures_admin_token')
    if (!isAdmin && !hasAdminToken) {
      next({ path: '/' })
      return
    }
  }
  next()
})

export default router
