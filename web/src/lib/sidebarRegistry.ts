/**
 * Pluggable sidebar registry — modules can register navigation items.
 *
 * Built-in items are registered at import time. 3rd party modules call
 * registerSidebarItem() to add their own sections/links.
 */

import type { ComponentType } from 'react'

export interface SidebarItem {
  /** Unique key for this item */
  id: string
  /** Which sidebar section: 'global' (Control Plane) or 'project' (per-project) */
  section: 'global' | 'project'
  /** Display label */
  label: string
  /** Icon (emoji or string) */
  icon: string
  /**
   * Route pattern. Use :project as placeholder for the current project name.
   * Examples: '/manager', '/manager/:project/issues', '/set/:project'
   */
  route: string
  /** Optional badge component — receives { project: string | null } props */
  badge?: ComponentType<{ project: string | null }>
  /** Sort order within section (lower = higher) */
  order: number
  /**
   * Route match patterns — used to determine if this item is "active".
   * If omitted, exact match on `route` is used.
   */
  matchPatterns?: string[]
}

const registry: SidebarItem[] = []

export function registerSidebarItem(item: SidebarItem): void {
  // Replace if same id exists (allows override)
  const idx = registry.findIndex(i => i.id === item.id)
  if (idx >= 0) {
    registry[idx] = item
  } else {
    registry.push(item)
  }
}

export function getSidebarItems(section?: 'global' | 'project'): SidebarItem[] {
  const items = section ? registry.filter(i => i.section === section) : registry
  return [...items].sort((a, b) => a.order - b.order)
}

export function unregisterSidebarItem(id: string): void {
  const idx = registry.findIndex(i => i.id === id)
  if (idx >= 0) registry.splice(idx, 1)
}

// --- Built-in items ---

// Global / Control Plane
registerSidebarItem({
  id: 'manager-overview',
  section: 'global',
  label: 'Overview',
  icon: '■',
  route: '/manager',
  order: 10,
})

registerSidebarItem({
  id: 'manager-all-issues',
  section: 'global',
  label: 'All Issues',
  icon: '⚠',
  route: '/manager/issues',
  order: 20,
})

// Per-project
registerSidebarItem({
  id: 'project-dashboard',
  section: 'project',
  label: 'Dashboard',
  icon: '📊',
  route: '/set/:project',
  matchPatterns: ['/set/:project', '/set/:project/'],
  order: 10,
})

registerSidebarItem({
  id: 'project-issues',
  section: 'project',
  label: 'Issues',
  icon: '⚠',
  route: '/manager/:project/issues',
  matchPatterns: ['/manager/:project/issues', '/manager/:project/issues/'],
  order: 20,
})

registerSidebarItem({
  id: 'project-sentinel',
  section: 'project',
  label: 'Sentinel',
  icon: '🛡',
  route: '/set/:project',  // sentinel is a tab on dashboard
  matchPatterns: [],  // never auto-active (it's a dashboard tab)
  order: 30,
})

registerSidebarItem({
  id: 'project-worktrees',
  section: 'project',
  label: 'Worktrees',
  icon: '📦',
  route: '/set/:project/worktrees',
  order: 40,
})

registerSidebarItem({
  id: 'project-memory',
  section: 'project',
  label: 'Memory',
  icon: '🧠',
  route: '/set/:project/memory',
  order: 50,
})

registerSidebarItem({
  id: 'project-settings',
  section: 'project',
  label: 'Settings',
  icon: '⚙',
  route: '/set/:project/settings',
  order: 60,
})

registerSidebarItem({
  id: 'project-mutes',
  section: 'project',
  label: 'Mute Patterns',
  icon: '🔇',
  route: '/manager/:project/mutes',
  order: 70,
})
