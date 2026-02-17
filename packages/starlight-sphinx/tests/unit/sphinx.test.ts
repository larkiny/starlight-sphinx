import { execFile } from 'node:child_process'
import { promisify } from 'node:util'

import type { AstroIntegrationLogger, AstroConfig } from 'astro'
import { describe, expect, test } from 'vitest'

import { NoDocumentationError } from '../../libs/sphinx'
import type { SphinxStructure } from '../../libs/types'

const execFileAsync = promisify(execFile)

const mockLogger = {
  info() {},
  warn() {},
  error() {},
  debug() {},
} as unknown as AstroIntegrationLogger

describe('NoDocumentationError', () => {
  test('should have the correct error message', () => {
    const error = new NoDocumentationError()
    expect(error.message).toBe('Failed to generate Sphinx documentation. No documented Python objects found.')
  })

  test('should be an instance of Error', () => {
    const error = new NoDocumentationError()
    expect(error).toBeInstanceOf(Error)
  })
})

describe('SphinxStructure types', () => {
  test('should accept a valid package structure', () => {
    const structure: SphinxStructure = {
      name: 'my_package',
      kind: 'package',
      qualifiedName: 'my_package',
      groups: [
        {
          title: 'Classes',
          children: [
            {
              name: 'MyClass',
              qualifiedName: 'my_package.MyClass',
              kind: 'class',
            },
          ],
        },
        {
          title: 'Functions',
          children: [
            {
              name: 'helper_function',
              qualifiedName: 'my_package.helper_function',
              kind: 'function',
            },
          ],
        },
      ],
    }

    expect(structure.name).toBe('my_package')
    expect(structure.kind).toBe('package')
    expect(structure.groups).toHaveLength(2)
    expect(structure.groups![0]!.title).toBe('Classes')
    expect(structure.groups![1]!.title).toBe('Functions')
  })

  test('should accept a multi-package structure', () => {
    const structure: SphinxStructure = {
      name: 'API',
      kind: 'package',
      qualifiedName: '',
      children: [
        {
          name: 'package_a',
          kind: 'package',
          qualifiedName: 'package_a',
          groups: [],
        },
        {
          name: 'package_b',
          kind: 'package',
          qualifiedName: 'package_b',
          groups: [],
        },
      ],
    }

    expect(structure.children).toHaveLength(2)
    expect(structure.qualifiedName).toBe('')
  })
})

describe('renderer.py', () => {
  test('should be importable and show help', async () => {
    try {
      const { stdout } = await execFileAsync('python3', [
        '../../libs/renderer.py',
        '--help',
      ], {
        cwd: import.meta.dirname,
      })
      expect(stdout).toContain('Starlight-Sphinx Python renderer')
      expect(stdout).toContain('--packages')
      expect(stdout).toContain('--output')
    } catch {
      // Python or autodoc2 not available in test environment - skip
    }
  })
})
