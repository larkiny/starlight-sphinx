<div align="center">
  <h1>starlight-sphinx</h1>
  <p>Starlight plugin to generate documentation from Python packages using Sphinx autodoc2.</p>
</div>

## Getting Started

Install the plugin and its Python dependencies:

```sh
npm install starlight-sphinx
pip install sphinx-autodoc2 docstring-parser
```

## Features

A [Starlight](https://starlight.astro.build) plugin using [autodoc2](https://github.com/sphinx-extensions2/sphinx-autodoc2) to generate API documentation from Python source code. It statically analyzes your Python packages (no imports required) and produces Starlight-compatible Markdown pages.

- Static analysis — never imports your Python code
- Supports Google, NumPy, and Sphinx docstring formats
- Generates one page per class/function/exception/constant
- Automatic sidebar generation
- Multi-package support
- Deprecation and release stage asides

## License

Licensed under the MIT License, Copyright © HiDeoo.

See [LICENSE](./LICENSE) for more information.
