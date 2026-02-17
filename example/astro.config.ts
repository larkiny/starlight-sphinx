import starlight from '@astrojs/starlight'
import { defineConfig } from 'astro/config'
import starlightSphinx, { sphinxSidebarGroup } from 'starlight-sphinx'

export default defineConfig({
  integrations: [
    starlight({
      customCss: ['./src/styles/custom.css'],
      plugins: [
        starlightSphinx({
          packages: ['../fixtures/python-basics/my_package'],
          sidebar: {
            label: 'Python API (auto-generated)',
          },
        }),
      ],
      sidebar: [
        {
          label: 'Guides',
          items: ['guides/example'],
        },
        sphinxSidebarGroup,
      ],
      title: 'Starlight Sphinx Example',
    }),
  ],
})
