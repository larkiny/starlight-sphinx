import { execFile } from 'node:child_process'
import * as fs from 'node:fs'
import path from 'node:path'
import url from 'node:url'
import { promisify } from 'node:util'

import type { AstroConfig, AstroIntegrationLogger } from 'astro'

import type { StarlightSphinxOptions } from '..'

import { getStarlightSphinxOutputDirectory } from './starlight'
import type { SphinxDefinitions, SphinxPackageConfig, SphinxStructure } from './types'

const execFileAsync = promisify(execFile)

const __dirname = path.dirname(url.fileURLToPath(import.meta.url))

export async function generateSphinxDocs(
  options: StarlightSphinxOptions,
  config: AstroConfig,
  logger: AstroIntegrationLogger,
): Promise<{
  definitions: SphinxDefinitions
  outputDirectory: string
  structure: SphinxStructure
}> {
  const outputDirectory = options.output ?? 'api'
  const outputPath = path.join(url.fileURLToPath(config.srcDir), 'content/docs', outputDirectory)

  const pythonPath = options.python ?? 'python3'

  await validatePython(pythonPath, logger)
  await validateAutodoc2(pythonPath, logger)
  await validateDocstringParser(pythonPath, logger)

  const packages = normalizePackages(options.packages)

  const rendererScript = path.join(__dirname, 'renderer.py')
  const baseUrl = getStarlightSphinxOutputDirectory(outputDirectory, config.base)

  const args = [
    rendererScript,
    '--packages',
    JSON.stringify(packages),
    '--output',
    outputPath,
    '--config',
    JSON.stringify(options.sphinxConfig ?? {}),
    '--base-url',
    baseUrl,
  ]

  if (options.pagination) {
    args.push('--pagination')
  }

  logger.info(`Generating Python documentation from ${packages.length} package(s)...`)

  let stdout: string

  try {
    const result = await execFileAsync(pythonPath, args, {
      maxBuffer: 50 * 1024 * 1024,
      timeout: 5 * 60 * 1000,
    })
    stdout = result.stdout

    if (result.stderr) {
      for (const line of result.stderr.split('\n')) {
        if (line.trim()) {
          logger.warn(line)
        }
      }
    }
  } catch (error) {
    const execError = error as { stderr?: string; message?: string }
    const errorMessage = execError.stderr || execError.message || 'Unknown error'
    throw new Error(`Failed to run Python renderer: ${errorMessage}`)
  }

  let manifest: SphinxManifest

  try {
    manifest = JSON.parse(stdout)
  } catch {
    throw new Error(`Failed to parse renderer output. Raw output:\n${stdout.slice(0, 500)}`)
  }

  if (!manifest.definitions || Object.keys(manifest.definitions).length === 0) {
    throw new NoDocumentationError()
  }

  logger.info(
    `Generated ${Object.keys(manifest.definitions).length} definitions across ${manifest.files.length} files.`,
  )

  return {
    definitions: manifest.definitions,
    outputDirectory,
    structure: manifest.structure,
  }
}

function normalizePackages(packages: StarlightSphinxOptions['packages']): SphinxPackageConfig[] {
  if (typeof packages === 'string') {
    return [{ path: packages }]
  }

  if (Array.isArray(packages)) {
    return packages.map((pkg) => {
      if (typeof pkg === 'string') {
        return { path: pkg }
      }
      return pkg
    })
  }

  return [packages as SphinxPackageConfig]
}

async function validatePython(pythonPath: string, logger: AstroIntegrationLogger): Promise<void> {
  try {
    const { stdout } = await execFileAsync(pythonPath, ['--version'])
    const version = stdout.trim()
    logger.info(`Using ${version}`)

    const match = version.match(/Python (\d+)\.(\d+)/)
    if (match) {
      const major = parseInt(match[1]!, 10)
      const minor = parseInt(match[2]!, 10)
      if (major < 3 || (major === 3 && minor < 9)) {
        throw new Error(`Python 3.9+ is required, found ${version}`)
      }
    }
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      throw new Error(
        `Python 3 not found at '${pythonPath}'. Install Python 3.9+ and ensure '${pythonPath}' is on your PATH, or set the 'python' option.`,
      )
    }
    throw error
  }
}

async function validateAutodoc2(pythonPath: string, logger: AstroIntegrationLogger): Promise<void> {
  try {
    await execFileAsync(pythonPath, ['-c', 'import autodoc2; print(autodoc2.__version__)'])
  } catch {
    throw new Error('autodoc2 is not installed. Install with: pip install sphinx-autodoc2')
  }
}

async function validateDocstringParser(pythonPath: string, logger: AstroIntegrationLogger): Promise<void> {
  try {
    await execFileAsync(pythonPath, ['-c', 'import docstring_parser'])
  } catch {
    throw new Error('docstring-parser is not installed. Install with: pip install docstring-parser')
  }
}

export class NoDocumentationError extends Error {
  constructor() {
    super('Failed to generate Sphinx documentation. No documented Python objects found.')
  }
}

interface SphinxManifest {
  structure: SphinxStructure
  definitions: SphinxDefinitions
  files: string[]
}
