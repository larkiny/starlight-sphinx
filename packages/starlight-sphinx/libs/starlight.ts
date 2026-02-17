import path from 'node:path'

import type { HookParameters } from '@astrojs/starlight/types'
import { slug } from 'github-slugger'

import type { StarlightSphinxSidebarOptions } from '..'

import type { SphinxDefinitions, SphinxStructure } from './types'

const externalLinkRegex = /^(http|ftp)s?:\/\//

const sidebarDefaultOptions = {
  collapsed: false,
  label: 'API',
} satisfies StarlightSphinxSidebarOptions

const starlightSphinxSidebarGroupLabel = Symbol('StarlightSphinxSidebarGroupLabel')

export function getSidebarGroupPlaceholder(label = starlightSphinxSidebarGroupLabel): SidebarGroup {
  return {
    items: [],
    label: label.toString(),
  }
}

export function getSidebarFromStructure(
  sidebar: StarlightUserConfigSidebar,
  sidebarGroupPlaceholder: SidebarGroup,
  options: StarlightSphinxSidebarOptions = {},
  structure: SphinxStructure,
  definitions: SphinxDefinitions,
  baseOutputDirectory: string,
): StarlightUserConfigSidebar {
  if (!sidebar || sidebar.length === 0) {
    return sidebar
  }

  const sidebarGroup = getSidebarGroupFromStructure(options, structure, definitions, baseOutputDirectory)

  function replaceSidebarGroupPlaceholder(group: SidebarManualGroup): SidebarGroup {
    if (group.label === sidebarGroupPlaceholder.label) {
      return group.badge ? { ...sidebarGroup, badge: group.badge } : sidebarGroup
    }

    if (isSidebarManualGroup(group)) {
      return {
        ...group,
        items: group.items.map((item) => {
          return isSidebarManualGroup(item) ? replaceSidebarGroupPlaceholder(item) : item
        }),
      }
    }

    return group
  }

  return sidebar.map((item) => {
    return isSidebarManualGroup(item) ? replaceSidebarGroupPlaceholder(item) : item
  })
}

export function getSidebarWithoutStructure(
  sidebar: StarlightUserConfigSidebar,
  sidebarGroupPlaceholder: SidebarGroup,
): StarlightUserConfigSidebar {
  if (!sidebar || sidebar.length === 0) {
    return sidebar
  }

  function removeSidebarGroupPlaceholder(
    entries: NonNullable<StarlightUserConfigSidebar>,
  ): NonNullable<StarlightUserConfigSidebar> {
    const sidebarWithoutPlaceholder: StarlightUserConfigSidebar = []

    for (const item of entries) {
      if (isSidebarManualGroup(item)) {
        if (item.label === sidebarGroupPlaceholder.label) continue

        sidebarWithoutPlaceholder.push({
          ...item,
          items: removeSidebarGroupPlaceholder(item.items),
        })
        continue
      }

      sidebarWithoutPlaceholder.push(item)
    }

    return sidebarWithoutPlaceholder
  }

  return removeSidebarGroupPlaceholder(sidebar)
}

function getSidebarGroupFromStructure(
  options: StarlightSphinxSidebarOptions,
  structure: SphinxStructure,
  definitions: SphinxDefinitions,
  baseOutputDirectory: string,
): SidebarGroup {
  const groups = structure.groups ?? []
  const children = structure.children ?? []

  // If we have multiple top-level packages (no qualifiedName = wrapper node)
  if (children.length > 0 && !structure.qualifiedName) {
    return {
      label: options.label ?? sidebarDefaultOptions.label,
      collapsed: options.collapsed ?? sidebarDefaultOptions.collapsed,
      items: children
        .map((child) => {
          return getSidebarGroupFromStructure(
            { collapsed: true, label: child.name },
            child,
            definitions,
            baseOutputDirectory,
          )
        })
        .filter((item): item is SidebarGroup => item !== undefined),
    }
  }

  const items: SidebarGroup[] = []

  for (const group of groups) {
    if (group.title === 'Modules') {
      for (const child of group.children) {
        const childStructure = children.find((c) => c.qualifiedName === child.qualifiedName)
        if (childStructure) {
          items.push(
            getSidebarGroupFromStructure(
              { collapsed: true, label: child.name },
              childStructure,
              definitions,
              baseOutputDirectory,
            ),
          )
        }
      }
    } else {
      const directory = `${baseOutputDirectory}/${slug(group.title.toLowerCase())}`

      const hasChildren = group.children.some((child) => {
        const defUrl = definitions[child.qualifiedName]
        return defUrl && defUrl.includes(`${slug(group.title.toLowerCase())}/`)
      })

      if (hasChildren) {
        items.push({
          collapsed: true,
          label: group.title,
          autogenerate: {
            collapsed: true,
            directory,
          },
        })
      }
    }
  }

  return {
    label: options.label ?? structure.name ?? sidebarDefaultOptions.label,
    collapsed: options.collapsed ?? sidebarDefaultOptions.collapsed,
    items,
  }
}

export function getAsideMarkdown(type: AsideType, title: string, content: string) {
  return `:::${type}[${title}]
${content}
:::`
}

export function getRelativeURL(url: string, baseUrl: string, pageUrl?: string): string {
  if (externalLinkRegex.test(url)) {
    return url
  }

  const currentDirname = path.dirname(pageUrl ?? '')
  const urlDirname = path.dirname(url)
  const relativeUrl =
    currentDirname === urlDirname ? url : path.posix.join(currentDirname, path.posix.relative(currentDirname, url))

  const filePath = path.parse(relativeUrl)
  const [, anchor] = filePath.base.split('#')
  const segments = filePath.dir
    .split(/[/\\]/)
    .map((segment) => slug(segment))
    .filter((segment) => segment !== '')

  let constructedUrl = typeof baseUrl === 'string' ? baseUrl : ''
  constructedUrl += segments.length > 0 ? `${segments.join('/')}/` : ''
  const fileNameSlug = slug(filePath.name)
  constructedUrl += fileNameSlug || filePath.name
  constructedUrl += '/'
  constructedUrl += anchor && anchor.length > 0 ? `#${anchor}` : ''

  return constructedUrl
}

export function getStarlightSphinxOutputDirectory(outputDirectory: string, base = '') {
  return path.posix.join(base, `/${outputDirectory}${outputDirectory.endsWith('/') ? '' : '/'}`)
}

function isSidebarManualGroup(item: NonNullable<StarlightUserConfigSidebar>[number]): item is SidebarManualGroup {
  return typeof item === 'object' && 'items' in item
}

export type SidebarGroup =
  | SidebarManualGroup
  | {
      autogenerate: {
        collapsed?: boolean
        directory: string
      }
      collapsed?: boolean
      label: string
    }

interface SidebarManualGroup {
  collapsed?: boolean
  items: (LinkItem | SidebarGroup)[]
  label: string
  badge?:
    | string
    | {
        text: string
        variant: 'note' | 'danger' | 'success' | 'caution' | 'tip' | 'default'
      }
    | undefined
}

interface LinkItem {
  label: string
  link: string
}

type AsideType = 'caution' | 'danger' | 'note' | 'tip'

type StarlightUserConfigSidebar = HookParameters<'config:setup'>['config']['sidebar']
