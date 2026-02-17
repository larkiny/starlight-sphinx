# Starlight-Sphinx Implementation Plan

## Refactoring starlight-typedoc → starlight-sphinx

This plan describes how to refactor the forked `starlight-typedoc` plugin to support
Python documentation generation using **Sphinx**, **myst_parser**, and **autodoc2**,
producing Starlight-compatible Markdown for ingestion into an Astro/Starlight documentation portal.

---

## Executive Summary

The existing `starlight-typedoc` plugin follows a clean architecture:

```
TypeScript Source → TypeDoc (AST) → typedoc-plugin-markdown → Markdown + Frontmatter → Starlight
```

We will replace the TypeDoc pipeline with a Sphinx/autodoc2 pipeline:

```
Python Source → autodoc2 (static AST analysis) → Custom Starlight Renderer → Markdown + Frontmatter → Starlight
```

The key insight is that **autodoc2's analysis layer is decoupled from Sphinx** — it uses
static AST parsing (never imports Python code) and has a standalone CLI/API. We can invoke
autodoc2's analysis from Node.js via a Python subprocess, then either:

- **Option A (Recommended):** Write a custom Python renderer extending autodoc2's `RendererBase`
  that outputs Starlight-compatible GFM Markdown directly (bypassing MyST directives entirely).
- **Option B:** Use autodoc2's MyST renderer output, then post-process it in Node.js to convert
  MyST directives/roles into GFM Markdown + Starlight frontmatter.

Option A is recommended because it avoids the lossy MyST→GFM conversion entirely.

---

## Architecture Overview

### Current Architecture (TypeDoc)

```
index.ts                   Entry point — Starlight plugin hook (config:setup)
  ├── libs/typedoc.ts      Bootstraps TypeDoc, generates MD files, injects frontmatter
  ├── libs/theme.ts        Custom TypeDoc theme (extends typedoc-plugin-markdown)
  ├── libs/starlight.ts    Sidebar generation from TypeDoc reflections
  ├── libs/markdown.ts     Frontmatter injection utility
  └── libs/logger.ts       Logger bridge (TypeDoc → Astro)
```

### Target Architecture (Sphinx)

```
index.ts                   Entry point — Starlight plugin hook (config:setup) [MODIFIED]
  ├── libs/sphinx.ts       NEW: Invokes autodoc2 analysis + custom renderer via Python subprocess
  ├── libs/renderer.py     NEW: Python script — custom autodoc2 renderer → Starlight Markdown
  ├── libs/starlight.ts    Sidebar generation from Sphinx structure [MODIFIED]
  ├── libs/markdown.ts     Frontmatter injection utility [UNCHANGED]
  └── libs/logger.ts       Logger bridge (simplified) [MODIFIED]

  # Removed:
  ├── libs/typedoc.ts      DELETED (replaced by libs/sphinx.ts)
  └── libs/theme.ts        DELETED (replaced by libs/renderer.py)
```

---

## Phase 1: Core Infrastructure

### 1.1 Rename Package and Update Metadata

**Files:** `packages/starlight-typedoc/package.json`, root `package.json`

- Rename package from `starlight-typedoc` to `starlight-sphinx`
- Update `description`, `keywords`, `homepage`, `repository`, `bugs` URLs
- Remove `peerDependencies` on `typedoc` and `typedoc-plugin-markdown`
- Keep `peerDependencies` on `@astrojs/starlight >=0.32.0`
- Keep `dependencies` on `github-slugger ^2.0.0`
- Add dependency on `execa` (for subprocess management) or use Node.js built-in `child_process`
- Update `exports` field: `".": "./index.ts"`
- Rename directory: `packages/starlight-typedoc/` → `packages/starlight-sphinx/`

### 1.2 Update Configuration Interface

**File:** `index.ts`

Replace `StarlightTypeDocOptions` with `StarlightSphinxOptions`:

```typescript
export interface StarlightSphinxOptions {
  /**
   * The path(s) to the Python package(s) to document.
   * Can be relative to the Astro project root.
   */
  packages: string | string[] | SphinxPackageConfig[]

  /**
   * The output directory for generated docs relative to `src/content/docs/`.
   * @default 'api'
   */
  output?: string

  /**
   * Sidebar configuration for the generated documentation.
   */
  sidebar?: StarlightSphinxSidebarOptions

  /**
   * Whether to include previous/next page links.
   * @default false
   */
  pagination?: boolean

  /**
   * Whether to error when no documentation is generated.
   * @default true
   */
  errorOnEmptyDocumentation?: boolean

  /**
   * Path to the Python executable. Uses 'python3' by default.
   * @default 'python3'
   */
  python?: string

  /**
   * Additional autodoc2/Sphinx configuration options.
   */
  sphinxConfig?: SphinxConfig
}

interface SphinxPackageConfig {
  /** Path to the Python package to document */
  path: string
  /** Override the module name (guessed from path if omitted) */
  module?: string
  /** Directories to exclude (fnmatch patterns) */
  excludeDirs?: string[]
  /** Files to exclude (fnmatch patterns) */
  excludeFiles?: string[]
}

interface SphinxConfig {
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

export interface StarlightSphinxSidebarOptions {
  collapsed?: boolean
  label?: string
}
```

### 1.3 Update Entry Point

**File:** `index.ts`

- Rename `starlightTypeDocPlugin` → `starlightSphinxPlugin`
- Rename `createStarlightTypeDocPlugin` → `createStarlightSphinxPlugin`
- Replace `generateTypeDoc` call with `generateSphinxDocs`
- Replace `NoReflectionsError` with `NoDocumentationError`
- Update sidebar generation to use new Sphinx-based structure types
- Keep the same Starlight plugin hook pattern (`config:setup`)

```typescript
// Core flow remains identical:
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
```

---

## Phase 2: Python Documentation Engine

### 2.1 Create Python Renderer Script

**File:** `packages/starlight-sphinx/libs/renderer.py`

This is the most critical new file. It's a standalone Python script that:

1. Uses `autodoc2.analysis.analyse_module()` to statically parse Python source
2. Builds an in-memory database of all discovered objects
3. Renders each object as **Starlight-compatible GFM Markdown** (not MyST)
4. Outputs a JSON manifest describing the generated files + structure

```python
#!/usr/bin/env python3
"""
starlight-sphinx renderer — converts Python source to Starlight-compatible Markdown.

Uses autodoc2's static analysis engine to parse Python packages without importing them,
then renders Starlight-compatible GitHub-Flavored Markdown with YAML frontmatter.

Usage:
    python renderer.py --packages '["../src/mypackage"]' --output ./docs/api --config '{...}'

Output:
    - Markdown files in the output directory
    - JSON manifest on stdout with structure + definitions
"""

import argparse
import json
import sys
import os
from pathlib import Path
from typing import Any

# Key autodoc2 imports:
# from autodoc2.analysis import analyse_module
# from autodoc2.db import InMemoryDb
# from autodoc2.render.base import RendererBase

# The script will:
# 1. Parse CLI arguments (packages, output dir, config)
# 2. For each package: run analyse_module() to get object records
# 3. Build InMemoryDb with all records
# 4. Walk the database, generating one .md file per module
# 5. For each object, render GFM markdown:
#    - Module → page title + module docstring
#    - Class → ### heading + bases + constructor + methods/properties
#    - Function → ### heading + signature + docstring
#    - Data/Attribute → ### heading + type + value + docstring
# 6. Add YAML frontmatter (title, editUrl: false, pagination)
# 7. Output JSON manifest to stdout:
#    {
#      "structure": { ... },     // Hierarchical module/class/function tree
#      "definitions": { ... },   // Object qualified name → relative URL
#      "files": [ ... ]          // List of generated file paths
#    }
```

**Rendering approach per object type:**

| Python Object | Rendered Markdown |
|---|---|
| **Module** | `# module_name` page title + module docstring body |
| **Class** | `## ClassName` heading + `**Bases:** [Base](link)` + constructor signature in code block + class docstring |
| **Method** | `### method_name()` heading + signature in code block + docstring + parameter table |
| **Function** | `## function_name()` heading + signature in code block + docstring + parameter table |
| **Property** | `### property_name` heading + type annotation + docstring |
| **Data/Constant** | `## CONSTANT_NAME` heading + type + value + docstring |
| **Exception** | Same as Class, with note indicating it's an exception |

**Docstring rendering:**

- Google-style and NumPy-style docstrings parsed via `docstring_parser` library
- Parameters → Markdown table: `| Parameter | Type | Description |`
- Returns → `**Returns:** type — description`
- Raises → `**Raises:** ExceptionType — description`
- Examples → fenced code blocks with `python` language tag
- Cross-references → Markdown links `[ClassName](./relative/path/)`
- Deprecation notices → Starlight `:::caution[Deprecated]` asides

**File organization:**

```
output/
  index.md                          # Package overview with module listing
  my_package/
    index.md                        # Package __init__ docs
    core.md                         # my_package.core module
    utils/
      index.md                      # my_package.utils subpackage
      helpers.md                    # my_package.utils.helpers module
```

### 2.2 Create Node.js Sphinx Integration

**File:** `packages/starlight-sphinx/libs/sphinx.ts`

Replaces `libs/typedoc.ts`. Responsible for:

1. Locating and validating the Python executable
2. Spawning the Python renderer subprocess
3. Parsing the JSON manifest output
4. Writing frontmatter-injected Markdown files to the Starlight content directory
5. Building the definitions map and structure tree for sidebar generation

```typescript
// Key exports:
export async function generateSphinxDocs(
  options: StarlightSphinxOptions,
  config: AstroConfig,
  logger: AstroIntegrationLogger,
): Promise<{
  definitions: SphinxDefinitions
  outputDirectory: string
  structure: SphinxStructure
}>

export class NoDocumentationError extends Error {
  constructor() {
    super('Failed to generate Sphinx documentation. No documented Python objects found.')
  }
}

export type SphinxDefinitions = Record<string, string> // qualifiedName → relativeUrl
```

**Implementation:**

```typescript
async function generateSphinxDocs(options, config, logger) {
  const outputDirectory = options.output ?? 'api'
  const outputPath = path.join(
    url.fileURLToPath(config.srcDir),
    'content/docs',
    outputDirectory,
  )

  // 1. Validate Python is available
  const pythonPath = options.python ?? 'python3'
  await validatePython(pythonPath)

  // 2. Validate autodoc2 is installed
  await validateAutodoc2(pythonPath)

  // 3. Build package config
  const packages = normalizePackages(options.packages)

  // 4. Spawn renderer.py subprocess
  const rendererScript = path.join(__dirname, 'renderer.py')
  const result = await execPythonRenderer(pythonPath, rendererScript, {
    packages,
    output: outputPath,
    config: options.sphinxConfig ?? {},
    pagination: options.pagination ?? false,
    baseUrl: getStarlightSphinxOutputDirectory(outputDirectory, config.base),
  })

  // 5. Parse manifest
  const manifest = JSON.parse(result.stdout)

  if (!manifest.definitions || Object.keys(manifest.definitions).length === 0) {
    throw new NoDocumentationError()
  }

  // 6. Post-process: inject any additional frontmatter if needed
  for (const file of manifest.files) {
    // Files already have frontmatter from the Python renderer,
    // but we can add slugs for special characters here
    postProcessFile(file, outputDirectory, config.base)
  }

  return {
    definitions: manifest.definitions,
    outputDirectory,
    structure: manifest.structure,
  }
}
```

### 2.3 Python Environment Validation

**Within `libs/sphinx.ts`:**

```typescript
async function validatePython(pythonPath: string): Promise<void> {
  // Check python3 is available and >= 3.9
  // Throws descriptive error if not found
}

async function validateAutodoc2(pythonPath: string): Promise<void> {
  // Check: python -c "import autodoc2; print(autodoc2.__version__)"
  // If missing, throw error with install instructions:
  // "autodoc2 is required. Install with: pip install sphinx-autodoc2"
}
```

---

## Phase 3: Sidebar Generation Refactoring

### 3.1 Define Sphinx Structure Types

**File:** `packages/starlight-sphinx/libs/types.ts` (NEW)

Create types that mirror the role of TypeDoc's `ProjectReflection` / `DeclarationReflection` / `ReflectionGroup` but for Python objects:

```typescript
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
```

### 3.2 Refactor Sidebar Generation

**File:** `packages/starlight-sphinx/libs/starlight.ts`

The sidebar generation logic is already well-abstracted. Changes needed:

1. Replace TypeDoc type imports with Sphinx structure types
2. Replace `ReflectionKind` checks with `SphinxObjectKind` checks
3. Replace `reflection.id` lookups with `qualifiedName` lookups
4. Replace `ReferenceReflection` handling with Sphinx re-export handling
5. Keep all URL generation, placeholder replacement, and autogenerate logic

**Key function signature changes:**

```typescript
// Before:
function getSidebarGroupFromReflections(
  options: StarlightTypeDocSidebarOptions,
  reflections: ProjectReflection | DeclarationReflection,
  definitions: TypeDocDefinitions,
  baseOutputDirectory: string,
  outputDirectory: string,
  label?: string,
): SidebarGroup

// After:
function getSidebarGroupFromStructure(
  options: StarlightSphinxSidebarOptions,
  structure: SphinxStructure,
  definitions: SphinxDefinitions,
  baseOutputDirectory: string,
  outputDirectory: string,
  label?: string,
): SidebarGroup
```

**Mapping TypeDoc concepts → Sphinx concepts in sidebar:**

| TypeDoc | Sphinx | Sidebar Behavior |
|---|---|---|
| `ReflectionKind.Module` | `kind === 'module'` or `kind === 'package'` | Creates collapsed subgroup |
| `ReflectionGroup` | `SphinxGroup` | Creates autogenerate directory |
| `group.title === 'Modules'` | `group.title === 'Modules'` or `'Subpackages'` | Creates nested navigation |
| `ReferenceReflection` | Re-exports (detected by autodoc2) | Creates manual link items |
| `group.title === 'Classes'` | `group.title === 'Classes'` | Directory-based autogenerate |
| `group.title === 'Functions'` | `group.title === 'Functions'` | Directory-based autogenerate |
| (n/a) | `group.title === 'Exceptions'` | New group type |
| (n/a) | `group.title === 'Data'` | New group type |

**Preserved functionality:**
- `getSidebarGroupPlaceholder()` — unchanged
- `getSidebarFromReflections()` → `getSidebarFromStructure()` — same placeholder replacement logic
- `getSidebarWithoutReflections()` — unchanged
- `getRelativeURL()` — unchanged
- `getStarlightTypeDocOutputDirectory()` → `getStarlightSphinxOutputDirectory()` — same logic
- `getAsideMarkdown()` — unchanged
- All sidebar type definitions — unchanged

---

## Phase 4: File Organization in Output

### 4.1 Output Directory Structure

The Python renderer will organize files mirroring Python package structure:

**Single package:**
```
src/content/docs/api/
  index.md                    # Package overview
  classes/
    MyClass.md
    AnotherClass.md
  functions/
    my_function.md
    another_function.md
  exceptions/
    MyError.md
  data/
    MY_CONSTANT.md
  subpackage/
    index.md                  # Subpackage overview
    classes/
      SubClass.md
    functions/
      sub_function.md
```

**Multiple packages:**
```
src/content/docs/api/
  package_a/
    index.md
    classes/...
    functions/...
  package_b/
    index.md
    classes/...
    functions/...
```

This mirrors the TypeDoc output pattern (one directory per kind) and is compatible with
Starlight's `autogenerate` sidebar directive.

### 4.2 Frontmatter Generation

Each generated Markdown file includes Starlight-compatible YAML frontmatter:

```yaml
---
title: "MyClass"
editUrl: false
prev: false  # unless pagination is enabled
next: false  # unless pagination is enabled
slug: api/classes/myclass  # only for names with special chars
---
```

This matches exactly what the current TypeDoc plugin produces.

---

## Phase 5: Markdown Rendering Details

### 5.1 Class Page Template

```markdown
---
title: "MyClass"
editUrl: false
---

**`class my_package.MyClass(arg1: str, arg2: int = 0)`**

**Bases:** [`BaseClass`](../classes/baseclass/)

The class docstring content goes here, rendered from the source docstring.

:::caution[Deprecated]
Use `NewClass` instead. This will be removed in v3.0.
:::

## Constructor

```python
MyClass(arg1: str, arg2: int = 0)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `arg1` | `str` | — | The first argument |
| `arg2` | `int` | `0` | The second argument |

## Methods

### do_something

```python
def do_something(self, param: str) -> bool
```

Method docstring here.

| Parameter | Type | Description |
|-----------|------|-------------|
| `param` | `str` | The parameter |

**Returns:** `bool` — Whether the operation succeeded.

### async_method

```python
async def async_method(self) -> None
```

Async method docstring.

## Properties

### name

```python
@property
name: str
```

The name property docstring.

## Class Attributes

### default_timeout

**Type:** `int` = `30`

The default timeout in seconds.
```

### 5.2 Function Page Template

```markdown
---
title: "my_function"
editUrl: false
---

**`my_package.my_function(x: int, y: int, *, verbose: bool = False) → int`**

The function docstring content.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `x` | `int` | — | The x coordinate |
| `y` | `int` | — | The y coordinate |
| `verbose` | `bool` | `False` | Enable verbose output |

**Returns:** `int` — The computed result.

**Raises:**
- `ValueError` — If x or y is negative.

**Example:**

```python
result = my_function(1, 2)
assert result == 3
```
```

### 5.3 Module Index Page Template

```markdown
---
title: "my_package.core"
editUrl: false
---

Module docstring content from `my_package/core.py`.

## Classes

| Class | Description |
|-------|-------------|
| [`MyClass`](./classes/myclass/) | Short description from first line of docstring |

## Functions

| Function | Description |
|----------|-------------|
| [`my_function()`](./functions/my_function/) | Short description |

## Data

| Name | Type | Description |
|------|------|-------------|
| [`MY_CONSTANT`](./data/my_constant/) | `int` | Short description |
```

### 5.4 Cross-Reference Resolution

The Python renderer builds a complete mapping of qualified names → URLs during generation.
All internal cross-references in docstrings are resolved to relative Markdown links.

```python
# Reference resolution map (built during rendering):
{
  "my_package.MyClass": "classes/myclass/",
  "my_package.MyClass.do_something": "classes/myclass/#do_something",
  "my_package.my_function": "functions/my_function/",
  "my_package.MY_CONSTANT": "data/my_constant/",
}
```

Docstring references like `:class:`MyClass`` or `` `MyClass` `` are converted to
`[MyClass](../classes/myclass/)` using this map.

---

## Phase 6: Testing

### 6.1 Create Python Test Fixtures

**Directory:** `fixtures/python-basics/`

```
fixtures/
  python-basics/
    my_package/
      __init__.py          # Package with docstring and __all__
      core.py              # Classes, functions, constants
      utils.py             # Helper functions
      exceptions.py        # Custom exceptions
      _internal.py         # Private module (should be excluded)
      subpackage/
        __init__.py
        helpers.py
  python-packages/
    package_a/
      __init__.py
      module_a.py
    package_b/
      __init__.py
      module_b.py
```

**Fixture content examples:**

```python
# fixtures/python-basics/my_package/core.py
"""Core module with primary classes and functions."""

MY_CONSTANT: int = 42
"""The answer to everything."""

class MyClass:
    """A well-documented class.

    This class demonstrates various documentation features.

    Args:
        name: The name of the instance.
        value: An optional value.

    Example:
        >>> obj = MyClass("test")
        >>> obj.name
        'test'
    """

    default_timeout: int = 30
    """Default timeout in seconds."""

    def __init__(self, name: str, value: int = 0) -> None: ...

    def do_something(self, param: str) -> bool:
        """Do something interesting.

        Args:
            param: The parameter to process.

        Returns:
            Whether the operation succeeded.

        Raises:
            ValueError: If param is empty.
        """
        ...

    @property
    def name(self) -> str:
        """The name of this instance."""
        ...

    async def async_method(self) -> None:
        """An async method."""
        ...

def helper_function(x: int, y: int) -> int:
    """Add two numbers.

    Args:
        x: First number.
        y: Second number.

    Returns:
        The sum.
    """
    ...

class DeprecatedClass:
    """An old class.

    .. deprecated:: 2.0
        Use :class:`MyClass` instead.
    """
    ...
```

### 6.2 Unit Tests

**File:** `packages/starlight-sphinx/tests/unit/sphinx.test.ts`

Replaces `typedoc.test.ts`:

```typescript
// Test cases:
// - Should throw error when no Python packages found
// - Should throw error when autodoc2 is not installed
// - Should generate docs in `src/content/docs/api` by default
// - Should generate docs in a custom output directory
// - Should handle single package
// - Should handle multiple packages
// - Should exclude private modules (_internal.py)
// - Should respect hiddenObjects configuration
// - Should generate correct frontmatter
// - Should support pagination option
// - Should handle packages with no documented objects
```

**File:** `packages/starlight-sphinx/tests/unit/sidebar.test.ts`

Minimal changes — test the same sidebar placeholder logic with Sphinx structure types:

```typescript
// Existing tests largely work — just need to update type constructors:
// - Replace ProjectReflection mock with SphinxStructure mock
// - Same placeholder replacement behavior expected
```

### 6.3 E2E Tests

**File:** `packages/starlight-sphinx/tests/e2e/basics/`

Mirror existing E2E test patterns but for Python documentation:

```typescript
// content.test.ts — verify generated page content
// sidebar.test.ts — verify sidebar structure
// pagination.test.ts — verify prev/next links
// slug.test.ts — verify URL slugification
```

### 6.4 Example Site

**Directory:** `example/`

Update the example Astro site to demonstrate Python documentation:

```typescript
// astro.config.ts
import starlight from '@astrojs/starlight'
import starlightSphinx from 'starlight-sphinx'

export default defineConfig({
  integrations: [
    starlight({
      title: 'My Python Library',
      plugins: [
        starlightSphinx({
          packages: ['../fixtures/python-basics/my_package'],
          output: 'api',
          sidebar: { label: 'Python API' },
        }),
      ],
    }),
  ],
})
```

---

## Phase 7: Developer Experience

### 7.1 Error Messages

Provide clear, actionable error messages:

```
[starlight-sphinx] Python 3 not found. Install Python 3.9+ and ensure 'python3' is on your PATH.
[starlight-sphinx] autodoc2 not found. Install with: pip install sphinx-autodoc2
[starlight-sphinx] docstring-parser not found. Install with: pip install docstring-parser
[starlight-sphinx] No documented Python objects found in 'my_package'. Check that your package path is correct.
[starlight-sphinx] Failed to analyze package 'my_package': <error details>
```

### 7.2 Python Dependency Management

The plugin requires these Python packages:

- `sphinx-autodoc2` — for static AST analysis
- `docstring-parser` — for parsing Google/NumPy/Sphinx docstring formats

**Installation options:**
1. Document as prerequisites: `pip install sphinx-autodoc2 docstring-parser`
2. Provide a `requirements.txt` in the plugin package
3. Optionally, auto-install into a venv on first run (stretch goal)

### 7.3 Watch Mode

Watch mode support via `chokidar` or Node.js `fs.watch` on the Python source directories:

```typescript
if (options.watch) {
  // Watch Python source files for changes
  // Re-run renderer.py on .py file changes
  // Debounce to avoid rapid re-runs
}
```

This is simpler than TypeDoc's watch mode since we control the subprocess lifecycle.

---

## Implementation Order

### Milestone 1: Minimum Viable Plugin
1. Rename package and update metadata (Phase 1.1)
2. Create new configuration interface (Phase 1.2)
3. Write `renderer.py` — core Python renderer for single package (Phase 2.1)
4. Write `sphinx.ts` — Node.js subprocess orchestration (Phase 2.2)
5. Update `index.ts` entry point (Phase 1.3)
6. Create Python test fixtures (Phase 6.1)
7. Verify single-package documentation generation end-to-end

### Milestone 2: Sidebar + Multi-Package
8. Define Sphinx structure types (Phase 3.1)
9. Refactor sidebar generation (Phase 3.2)
10. Add multi-package support to renderer (Phase 4.1)
11. Unit tests for sidebar + generation (Phase 6.2)

### Milestone 3: Polish + Testing
12. Cross-reference resolution (Phase 5.4)
13. All docstring format support (Phase 5.1-5.3)
14. E2E tests (Phase 6.3)
15. Example site (Phase 6.4)
16. Error messages + validation (Phase 7.1-7.2)

### Milestone 4: Advanced Features
17. Watch mode (Phase 7.3)
18. Deprecation/aside rendering
19. Exception documentation
20. Property and class attribute rendering

---

## File Change Summary

| File | Action | Description |
|------|--------|-------------|
| `packages/starlight-typedoc/` | **RENAME** | → `packages/starlight-sphinx/` |
| `package.json` (root) | **MODIFY** | Update workspace references, keywords, description |
| `packages/starlight-sphinx/package.json` | **MODIFY** | New name, deps, peer deps, keywords |
| `packages/starlight-sphinx/index.ts` | **REWRITE** | New config interface, new function names, same hook pattern |
| `packages/starlight-sphinx/libs/typedoc.ts` | **DELETE** | Replaced by `sphinx.ts` |
| `packages/starlight-sphinx/libs/theme.ts` | **DELETE** | Replaced by `renderer.py` |
| `packages/starlight-sphinx/libs/sphinx.ts` | **CREATE** | Python subprocess orchestration + doc generation |
| `packages/starlight-sphinx/libs/renderer.py` | **CREATE** | autodoc2-based Python → Markdown renderer |
| `packages/starlight-sphinx/libs/types.ts` | **CREATE** | SphinxStructure, SphinxGroup, SphinxObjectKind types |
| `packages/starlight-sphinx/libs/starlight.ts` | **MODIFY** | Replace TypeDoc types with Sphinx types, keep logic |
| `packages/starlight-sphinx/libs/markdown.ts` | **KEEP** | No changes needed |
| `packages/starlight-sphinx/libs/logger.ts` | **SIMPLIFY** | Remove TypeDoc logger dependency |
| `fixtures/python-basics/` | **CREATE** | Python test fixtures |
| `fixtures/python-packages/` | **CREATE** | Multi-package test fixtures |
| `fixtures/basics/` | **DELETE** | TypeScript fixtures no longer needed |
| `fixtures/packages/` | **DELETE** | TypeScript fixtures no longer needed |
| `tests/unit/typedoc.test.ts` | **DELETE** | Replaced by `sphinx.test.ts` |
| `tests/unit/sidebar.test.ts` | **MODIFY** | Update types, keep test logic |
| `tests/unit/sphinx.test.ts` | **CREATE** | New unit tests for Sphinx generation |
| `tests/e2e/**` | **REWRITE** | Python fixture-based E2E tests |
| `example/` | **REWRITE** | Python documentation example |

---

## Key Design Decisions

### Why bypass Sphinx entirely and use autodoc2 directly?

1. **No Sphinx build step required** — faster, simpler, fewer dependencies
2. **No MyST→GFM conversion** — generate Starlight Markdown directly, avoiding lossy conversion
3. **autodoc2's analysis is decoupled** — it uses static AST parsing, not Python imports
4. **Simpler subprocess interface** — one Python script with JSON output vs. full Sphinx configuration
5. **No conf.py needed** — all configuration via the Starlight plugin options

### Why a Python subprocess instead of a pure Node.js solution?

1. **autodoc2 is Python-only** — no JavaScript equivalent with the same quality of AST analysis
2. **Python docstring parsing** — `docstring_parser` handles Google/NumPy/Sphinx formats reliably
3. **Python AST** — Python's own AST module is the most reliable parser for Python source
4. **Subprocess overhead is minimal** — runs once at build time, not in a hot path

### Why one file per object instead of one file per module?

1. **Matches Starlight's navigation model** — each page is a sidebar item
2. **Matches TypeDoc's output pattern** — familiar to existing starlight-typedoc users
3. **Better for search** — each object is independently searchable
4. **Supports autogenerate** — Starlight's directory-based sidebar works with this structure

---

## Dependencies

### Node.js (package.json)
- `@astrojs/starlight >=0.32.0` (peer dependency — unchanged)
- `github-slugger ^2.0.0` (dependency — unchanged)

### Python (requirements)
- `sphinx-autodoc2 >=0.5.0` (required — provides static analysis)
- `docstring-parser >=0.16` (required — parses docstring formats)
- Python >= 3.9 (required — for AST features)
