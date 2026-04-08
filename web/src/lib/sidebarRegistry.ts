/**
 * Pluggable sidebar registry — app-based two-level navigation.
 *
 * Level 1: Apps (Orchestration, Sentinel, Issues, Memory, Settings)
 * Level 2: Sub-items within the selected app
 *
 * Built-in apps are registered at import time. 3rd party plugins call
 * registerApp() to add their own top-level apps.
 */

import type { ComponentType } from 'react'
import type { LucideIcon } from 'lucide-react'
import { LayoutDashboard, TriangleAlert, BrainCircuit, Settings, SquareStack } from 'lucide-react'

export interface SidebarSubItem {
  id: string
  label: string
  /** Route pattern. Use :name as placeholder for the current project name. */
  route: string
  /** Route match patterns for active state detection. If omitted, exact match on route. */
  matchPatterns?: string[]
  /** Optional badge component */
  badge?: ComponentType<{ project: string | null }>
}

export interface SidebarApp {
  id: string
  label: string
  icon: string | LucideIcon
  /** Sort order (lower = higher in list) */
  order: number
  /** Default route when clicking the app — use :name as project placeholder */
  defaultRoute: string
  /** Match patterns to detect this app is active from URL */
  matchPatterns?: string[]
  children: SidebarSubItem[]
}

export interface GlobalItem {
  id: string
  label: string
  icon: string | LucideIcon
  route: string
  order: number
  badge?: ComponentType<{ project: string | null }>
}

const appRegistry: SidebarApp[] = []
const globalRegistry: GlobalItem[] = []

export function registerApp(app: SidebarApp): void {
  const idx = appRegistry.findIndex(a => a.id === app.id)
  if (idx >= 0) {
    appRegistry[idx] = app
  } else {
    appRegistry.push(app)
  }
}

export function registerGlobalItem(item: GlobalItem): void {
  const idx = globalRegistry.findIndex(i => i.id === item.id)
  if (idx >= 0) {
    globalRegistry[idx] = item
  } else {
    globalRegistry.push(item)
  }
}

export function getApps(): SidebarApp[] {
  return [...appRegistry].sort((a, b) => a.order - b.order)
}

export function getGlobalItems(): GlobalItem[] {
  return [...globalRegistry].sort((a, b) => a.order - b.order)
}

/** @deprecated Use registerApp() instead. Wraps a flat item into a single-child app. */
export function registerSidebarItem(item: {
  id: string
  section: 'global' | 'project'
  label: string
  icon: string
  route: string
  badge?: ComponentType<{ project: string | null }>
  order: number
  matchPatterns?: string[]
}): void {
  if (item.section === 'global') {
    registerGlobalItem({
      id: item.id,
      label: item.label,
      icon: item.icon,
      route: item.route,
      order: item.order,
      badge: item.badge,
    })
  } else {
    // Wrap as a single-child app for backwards compat
    registerApp({
      id: item.id,
      label: item.label,
      icon: item.icon,
      order: item.order,
      defaultRoute: item.route,
      matchPatterns: item.matchPatterns,
      children: [],
    })
  }
}

/** @deprecated Use getApps() or getGlobalItems() instead. */
export function getSidebarItems(section?: 'global' | 'project') {
  if (section === 'global') {
    return getGlobalItems().map(g => ({ ...g, section: 'global' as const }))
  }
  return getApps().map(a => ({ ...a, section: 'project' as const, route: a.defaultRoute }))
}

export function unregisterApp(id: string): void {
  const idx = appRegistry.findIndex(a => a.id === id)
  if (idx >= 0) appRegistry.splice(idx, 1)
}

// --- Built-in global items ---

registerGlobalItem({
  id: 'global-overview',
  label: 'Overview',
  icon: SquareStack,
  route: '/',
  order: 10,
})

registerGlobalItem({
  id: 'global-all-issues',
  label: 'All Issues',
  icon: TriangleAlert,
  route: '/issues',
  order: 20,
})

// --- Built-in apps ---

// Orchestration — the main dashboard with tabs (Changes, Phases, Log, etc.)
registerApp({
  id: 'orchestration',
  label: 'Orchestration',
  icon: LayoutDashboard,
  order: 10,
  defaultRoute: '/p/:name/orch',
  matchPatterns: ['/p/:name/orch'],
  children: [],  // tabs live in Dashboard content, not sidebar
})

registerApp({
  id: 'issues',
  label: 'Issues',
  icon: TriangleAlert,
  order: 30,
  defaultRoute: '/p/:name/issues',
  matchPatterns: ['/p/:name/issues'],
  children: [],
})

registerApp({
  id: 'memory',
  label: 'Memory',
  icon: BrainCircuit,
  order: 40,
  defaultRoute: '/p/:name/memory',
  matchPatterns: ['/p/:name/memory'],
  children: [],
})

registerApp({
  id: 'settings',
  label: 'Settings',
  icon: Settings,
  order: 50,
  defaultRoute: '/p/:name/settings',
  matchPatterns: ['/p/:name/settings'],
  children: [],
})
