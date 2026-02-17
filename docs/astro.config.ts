import starlight from '@astrojs/starlight'
import { defineConfig } from 'astro/config'

const site =
  process.env['VERCEL_ENV'] !== 'production' && process.env['VERCEL_URL']
    ? `https://${process.env['VERCEL_URL']}`
    : 'https://starlight-sphinx.vercel.app/'

export default defineConfig({
  integrations: [
    starlight({
      customCss: ['./src/styles/custom.css'],
      sidebar: [
        {
          label: 'Start Here',
          items: [
            { label: 'Getting Started', link: '/getting-started/' },
            { label: 'Configuration', link: '/configuration/' },
          ],
        },
        {
          label: 'Guides',
          items: [{ label: 'Multiple Instances', link: '/guides/multiple-instances/' }],
        },
      ],
      title: 'Starlight Sphinx',
    }),
  ],
  site,
})
