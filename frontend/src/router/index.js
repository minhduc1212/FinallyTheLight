import { createRouter, createWebHashHistory } from 'vue-router'

import Landing from '../views/Landing.vue'
import Dashboard from '../views/Dashboard.vue'
import Projects from '../views/Projects.vue'
import Settings from '../views/Settings.vue'
import ProjectDetail from '../views/ProjectDetail.vue'
import NovelChunks from '../views/NovelChunks.vue'
import Glossary from '../views/Glossary.vue'

const routes = [
  {
    path: '/',
    name: 'Landing',
    component: Landing,
  },
  {
    path: '/dashboard',
    component: Dashboard,
    children: [
      {
        path: '',
        name: 'Projects',
        component: Projects,
      },
      {
        path: 'projects',
        name: 'ProjectsList',
        component: Projects,
      },
      {
        path: 'settings',
        name: 'Settings',
        component: Settings,
      },
      {
        path: ':project',
        name: 'ProjectDetail',
        component: ProjectDetail,
        props: true,
      },
      {
        path: ':project/novels/:novel',
        name: 'NovelChunks',
        component: NovelChunks,
        props: true,
      },
      {
        path: ':project/glossary',
        name: 'Glossary',
        component: Glossary,
        props: true,
      },
    ],
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
