import { randomBytes } from 'node:crypto'

import type { StarlightPlugin } from '@astrojs/starlight/types'

import {
  getSidebarFromStructure,
  getSidebarGroupPlaceholder,
  getSidebarWithoutStructure,
  type SidebarGroup,
} from './libs/starlight'
import { generateSphinxDocs, NoDocumentationError } from './libs/sphinx'
import type { SphinxConfig, SphinxPackageConfig } from './libs/types'

export const sphinxSidebarGroup = getSidebarGroupPlaceholder()

export default function starlightSphinxPlugin(options: StarlightSphinxOptions): StarlightPlugin {
  return makeStarlightSphinxPlugin(sphinxSidebarGroup)(options)
}

export function createStarlightSphinxPlugin(): [plugin: typeof starlightSphinxPlugin, sidebarGroup: SidebarGroup] {
  const sidebarGroup = getSidebarGroupPlaceholder(Symbol(randomBytes(24).toString('base64url')))

  return [makeStarlightSphinxPlugin(sidebarGroup), sidebarGroup]
}

function makeStarlightSphinxPlugin(sidebarGroup: SidebarGroup): (options: StarlightSphinxOptions) => StarlightPlugin {
  return function starlightSphinxPlugin(options: StarlightSphinxOptions) {
    return {
      name: 'starlight-sphinx-plugin',
      hooks: {
        async 'config:setup'({ astroConfig, command, config, logger, updateConfig }) {
          if (command === 'preview') return

          try {
            const { definitions, outputDirectory, structure } = await generateSphinxDocs(options, astroConfig, logger)

            updateConfig({
              sidebar: getSidebarFromStructure(
                config.sidebar,
                sidebarGroup,
                options.sidebar,
                structure,
                definitions,
                outputDirectory,
              ),
            })
          } catch (error) {
            if (options.errorOnEmptyDocumentation === false && error instanceof NoDocumentationError) {
              logger.warn('No documentation generated but ignoring as `errorOnEmptyDocumentation` is disabled.')
              updateConfig({ sidebar: getSidebarWithoutStructure(config.sidebar, sidebarGroup) })
              return
            }

            throw error
          }
        },
      },
    }
  }
}

export interface StarlightSphinxOptions {
  /**
   * The path(s) to the Python package(s) to document.
   * Can be relative to the Astro project root.
   */
  packages: string | string[] | SphinxPackageConfig[]
  /**
   * Whether the plugin should error when no documentation is generated.
   * @default true
   */
  errorOnEmptyDocumentation?: boolean
  /**
   * The output directory containing the generated documentation markdown files relative to the `src/content/docs/`
   * directory.
   * @default 'api'
   */
  output?: string
  /**
   * The sidebar configuration for the generated documentation.
   */
  sidebar?: StarlightSphinxSidebarOptions
  /**
   * Whether the footer should include previous and next page links for the generated documentation.
   * @default false
   */
  pagination?: boolean
  /**
   * Path to the Python executable.
   * @default 'python3'
   */
  python?: string
  /**
   * Additional Sphinx/autodoc2 configuration options.
   */
  sphinxConfig?: SphinxConfig
}

export interface StarlightSphinxSidebarOptions {
  /**
   * Whether the generated documentation sidebar group should be collapsed by default.
   * Note that nested sidebar groups are always collapsed.
   * @default false
   */
  collapsed?: boolean
  /**
   * The generated documentation sidebar group label.
   * @default 'API'
   */
  label?: string
}
