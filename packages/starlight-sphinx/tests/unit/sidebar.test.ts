import { describe, expect, test } from 'vitest'

import { sphinxSidebarGroup } from '../../index'
import { getSidebarFromStructure, getSidebarWithoutStructure } from '../../libs/starlight'
import type { SphinxStructure } from '../../libs/types'

const gettingStartedLink = {
  label: 'Getting Started',
  link: '/guides/getting-started/',
}

const emptyStructure: SphinxStructure = {
  name: 'my_package',
  kind: 'package',
  qualifiedName: 'my_package',
}

describe('getSidebarFromStructure', () => {
  test('should not do anything for an undefined sidebar', () => {
    expect(getTestSidebar([])).toEqual([])
  })

  test('should not do anything for an empty sidebar', () => {
    expect(getTestSidebar([])).toEqual([])
  })

  test('should not do anything for a sidebar without a placeholder', () => {
    expect(getTestSidebar([gettingStartedLink])).toEqual([gettingStartedLink])
  })

  test('should replace a placeholder at the root level', () => {
    expect(getTestSidebar([gettingStartedLink, sphinxSidebarGroup])).toMatchInlineSnapshot(`
      [
        {
          "label": "Getting Started",
          "link": "/guides/getting-started/",
        },
        {
          "collapsed": false,
          "items": [],
          "label": "my_package",
        },
      ]
    `)
  })

  test('should replace a nested placeholder', () => {
    expect(
      getTestSidebar([
        {
          label: 'Guides',
          items: [sphinxSidebarGroup, gettingStartedLink],
        },
      ]),
    ).toMatchInlineSnapshot(`
      [
        {
          "items": [
            {
              "collapsed": false,
              "items": [],
              "label": "my_package",
            },
            {
              "label": "Getting Started",
              "link": "/guides/getting-started/",
            },
          ],
          "label": "Guides",
        },
      ]
    `)
  })

  test('should replace multiple placeholders', () => {
    expect(
      getTestSidebar([
        gettingStartedLink,
        {
          label: 'Guides',
          items: [gettingStartedLink, sphinxSidebarGroup],
        },
        sphinxSidebarGroup,
      ]),
    ).toMatchInlineSnapshot(`
      [
        {
          "label": "Getting Started",
          "link": "/guides/getting-started/",
        },
        {
          "items": [
            {
              "label": "Getting Started",
              "link": "/guides/getting-started/",
            },
            {
              "collapsed": false,
              "items": [],
              "label": "my_package",
            },
          ],
          "label": "Guides",
        },
        {
          "collapsed": false,
          "items": [],
          "label": "my_package",
        },
      ]
    `)
  })
})

describe('getSidebarWithoutStructure', () => {
  test('should not do anything for an undefined sidebar', () => {
    expect(getTestSidebarWithoutStructure([])).toEqual([])
  })

  test('should not do anything for an empty sidebar', () => {
    expect(getTestSidebarWithoutStructure([])).toEqual([])
  })

  test('should not do anything for a sidebar without a placeholder', () => {
    expect(getTestSidebarWithoutStructure([gettingStartedLink])).toEqual([gettingStartedLink])
  })

  test('should remove a placeholder at the root level', () => {
    expect(getTestSidebarWithoutStructure([gettingStartedLink, sphinxSidebarGroup])).toMatchInlineSnapshot(`
      [
        {
          "label": "Getting Started",
          "link": "/guides/getting-started/",
        },
      ]
    `)
  })

  test('should remove a nested placeholder', () => {
    expect(
      getTestSidebarWithoutStructure([
        {
          label: 'Guides',
          items: [sphinxSidebarGroup, gettingStartedLink],
        },
      ]),
    ).toMatchInlineSnapshot(`
      [
        {
          "items": [
            {
              "label": "Getting Started",
              "link": "/guides/getting-started/",
            },
          ],
          "label": "Guides",
        },
      ]
    `)
  })

  test('should remove multiple placeholders', () => {
    expect(
      getTestSidebarWithoutStructure([
        gettingStartedLink,
        {
          label: 'Guides',
          items: [gettingStartedLink, sphinxSidebarGroup],
        },
        sphinxSidebarGroup,
      ]),
    ).toMatchInlineSnapshot(`
      [
        {
          "label": "Getting Started",
          "link": "/guides/getting-started/",
        },
        {
          "items": [
            {
              "label": "Getting Started",
              "link": "/guides/getting-started/",
            },
          ],
          "label": "Guides",
        },
      ]
    `)
  })
})

function getTestSidebar(sidebar: Parameters<typeof getSidebarFromStructure>[0]) {
  return getSidebarFromStructure(sidebar, sphinxSidebarGroup, {}, emptyStructure, {}, 'api')
}

function getTestSidebarWithoutStructure(sidebar: Parameters<typeof getSidebarFromStructure>[0]) {
  return getSidebarWithoutStructure(sidebar, sphinxSidebarGroup)
}
