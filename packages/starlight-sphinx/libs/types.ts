export interface SphinxStructure {
  /** The root package/module name */
  name: string
  /** Type of this node */
  kind: SphinxObjectKind
  /** Qualified Python name */
  qualifiedName: string
  /** Child modules/subpackages */
  children?: SphinxStructure[]
  /** Grouped children by kind (classes, functions, etc.) */
  groups?: SphinxGroup[]
}

export interface SphinxGroup {
  /** Group title: 'Classes', 'Functions', 'Data', 'Exceptions', etc. */
  title: string
  /** Objects in this group */
  children: SphinxGroupChild[]
}

export interface SphinxGroupChild {
  /** Display name */
  name: string
  /** Qualified name (used as definition key) */
  qualifiedName: string
  /** Object kind */
  kind: SphinxObjectKind
}

export type SphinxObjectKind =
  | 'package'
  | 'module'
  | 'class'
  | 'function'
  | 'method'
  | 'property'
  | 'data'
  | 'exception'

export type SphinxDefinitions = Record<string, string>

export interface SphinxPackageConfig {
  /** Path to the Python package to document */
  path: string
  /** Override the module name (guessed from path if omitted) */
  module?: string
  /** Directories to exclude (fnmatch patterns) */
  excludeDirs?: string[]
  /** Files to exclude (fnmatch patterns) */
  excludeFiles?: string[]
}

export interface SphinxConfig {
  /** Object types to hide: 'private' | 'dunder' | 'inherited' */
  hiddenObjects?: ('private' | 'dunder' | 'inherited')[]
  /** Docstring format: 'google' | 'numpy' | 'sphinx' | 'myst' */
  docstringStyle?: 'google' | 'numpy' | 'sphinx' | 'myst'
  /** Whether to include class __init__ docstrings */
  includeInit?: boolean
  /** Whether to include module-level docstrings */
  includeModuleDocstring?: boolean
  /** Additional autodoc2 configuration as key-value pairs */
  extra?: Record<string, unknown>
}
