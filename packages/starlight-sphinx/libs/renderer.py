#!/usr/bin/env python3
"""
starlight-sphinx renderer — converts Python source to Starlight-compatible Markdown.

Uses autodoc2's static analysis engine to parse Python packages without importing them,
then renders Starlight-compatible GitHub-Flavored Markdown with YAML frontmatter.

Usage:
    python renderer.py --packages '[{"path": "../src/mypackage"}]' --output ./docs/api --config '{}'

Output:
    - Markdown files in the output directory
    - JSON manifest on stdout with structure + definitions
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

try:
    from autodoc2.analysis import analyse_module
    from autodoc2.db import InMemoryDb
except ImportError:
    print(
        "Error: autodoc2 is not installed. Install with: pip install sphinx-autodoc2",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    import docstring_parser
except ImportError:
    print(
        "Error: docstring-parser is not installed. Install with: pip install docstring-parser",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def slugify(name: str) -> str:
    """Convert a name to a URL-safe slug."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def escape_frontmatter(value: str) -> str:
    """Escape a value for YAML frontmatter."""
    if any(c in value for c in ":{}[]#&*!|>'\"%@`"):
        return f'"{value}"'
    return value


def make_frontmatter(
    title: str, pagination: bool, extra: dict[str, Any] | None = None
) -> str:
    """Generate YAML frontmatter."""
    lines = ["---"]
    lines.append(f"title: {escape_frontmatter(title)}")
    lines.append("editUrl: false")
    if not pagination:
        lines.append("prev: false")
        lines.append("next: false")
    if extra:
        for key, value in extra.items():
            if isinstance(value, bool):
                lines.append(f"{key}: {'true' if value else 'false'}")
            else:
                lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def short_description(docstring: str | None) -> str:
    """Extract first line/sentence from a docstring."""
    if not docstring:
        return ""
    first_line = docstring.strip().split("\n")[0].strip()
    return first_line


def format_type(annotation: str | None) -> str:
    """Format a type annotation for display."""
    if not annotation:
        return ""
    return f"`{annotation}`"


def build_param_table(
    parsed: "docstring_parser.Docstring", params: list[dict[str, Any]]
) -> str:
    """Build a markdown parameter table from parsed docstring + signature params."""
    if not params:
        return ""

    # Merge info from docstring and signature
    doc_params = {p.arg_name: p for p in parsed.params}

    rows = []
    for param in params:
        name = param.get("name", "")
        if name in ("self", "cls"):
            continue
        type_str = param.get("annotation", "")
        default = param.get("default", None)
        doc_param = doc_params.get(name)
        description = doc_param.description if doc_param else ""
        type_from_doc = doc_param.type_name if doc_param else None

        display_type = format_type(type_str or type_from_doc or "")
        display_default = f"`{default}`" if default else "\u2014"
        rows.append(
            f"| `{name}` | {display_type} | {display_default} | {description or ''} |"
        )

    if not rows:
        return ""

    header = "| Parameter | Type | Default | Description |"
    separator = "|-----------|------|---------|-------------|"
    return "\n".join([header, separator] + rows)


# ---------------------------------------------------------------------------
# Object renderers
# ---------------------------------------------------------------------------


class MarkdownRenderer:
    """Renders Python objects to Starlight-compatible GFM Markdown."""

    def __init__(
        self,
        db: InMemoryDb,
        output_dir: Path,
        base_url: str,
        pagination: bool,
        config: dict[str, Any],
    ):
        self.db = db
        self.output_dir = output_dir
        self.base_url = base_url.rstrip("/")
        self.pagination = pagination
        self.config = config
        self.definitions: dict[str, str] = {}
        self.files: list[str] = []
        self.docstring_style = config.get("docstringStyle", "google")
        self.hidden_objects: list[str] = config.get("hiddenObjects", ["private"])
        self.include_init = config.get("includeInit", True)
        self.include_module_docstring = config.get("includeModuleDocstring", True)

    def should_skip(self, item: dict[str, Any]) -> bool:
        """Check if an item should be skipped based on config."""
        full_name: str = item.get("full_name", "")
        short_name: str = full_name.rsplit(".", 1)[-1] if full_name else ""

        if "private" in self.hidden_objects and short_name.startswith("_") and not short_name.startswith("__"):
            return True
        if "dunder" in self.hidden_objects and short_name.startswith("__") and short_name.endswith("__"):
            if short_name != "__init__":
                return True
        return False

    def parse_docstring(self, docstring: str | None) -> "docstring_parser.Docstring":
        """Parse a docstring using the configured style."""
        style_map = {
            "google": docstring_parser.DocstringStyle.GOOGLE,
            "numpy": docstring_parser.DocstringStyle.NUMPYDOC,
            "sphinx": docstring_parser.DocstringStyle.REST,
        }
        style = style_map.get(self.docstring_style, docstring_parser.DocstringStyle.GOOGLE)
        return docstring_parser.parse(docstring or "", style=style)

    def render_docstring_body(self, parsed: "docstring_parser.Docstring") -> str:
        """Render the main body of a parsed docstring."""
        parts: list[str] = []
        if parsed.short_description:
            parts.append(parsed.short_description)
        if parsed.long_description:
            parts.append(parsed.long_description)
        return "\n\n".join(parts)

    def render_returns(self, parsed: "docstring_parser.Docstring") -> str:
        """Render return value documentation."""
        if not parsed.returns:
            return ""
        ret = parsed.returns
        type_str = format_type(ret.type_name) if ret.type_name else ""
        desc = ret.description or ""
        if type_str and desc:
            return f"**Returns:** {type_str} \u2014 {desc}"
        elif type_str:
            return f"**Returns:** {type_str}"
        elif desc:
            return f"**Returns:** {desc}"
        return ""

    def render_raises(self, parsed: "docstring_parser.Docstring") -> str:
        """Render raises documentation."""
        if not parsed.raises:
            return ""
        lines = ["**Raises:**"]
        for exc in parsed.raises:
            type_str = f"`{exc.type_name}`" if exc.type_name else "Exception"
            desc = exc.description or ""
            lines.append(f"- {type_str} \u2014 {desc}")
        return "\n".join(lines)

    def render_examples(self, parsed: "docstring_parser.Docstring") -> str:
        """Render example sections."""
        examples = [
            m for m in parsed.meta
            if isinstance(m, docstring_parser.DocstringMeta)
            and m.key in ("example", "examples")
        ]
        if not examples:
            return ""
        parts = ["**Example:**"]
        for ex in examples:
            desc = ex.description or ""
            if desc:
                parts.append(f"\n```python\n{desc}\n```")
        return "\n".join(parts)

    def render_deprecation(self, parsed: "docstring_parser.Docstring") -> str:
        """Render deprecation notice as a Starlight aside."""
        dep = parsed.deprecation
        if not dep:
            return ""
        content = dep.description or "This API is no longer supported and may be removed in a future release."
        return f":::caution[Deprecated]\n{content}\n:::"

    def get_signature(self, item: dict[str, Any]) -> str:
        """Extract the function/method signature."""
        args = item.get("args", [])
        if not args:
            return "()"

        parts = []
        seen_keyword_only = False
        for arg in args:
            name = arg.get("name", "")
            annotation = arg.get("annotation", "")
            default = arg.get("default", None)

            if name == "self" or name == "cls":
                continue

            if arg.get("kind") == "keyword_only" and not seen_keyword_only:
                parts.append("*")
                seen_keyword_only = True

            part = name
            if annotation:
                part = f"{name}: {annotation}"
            if default:
                part = f"{part} = {default}"
            parts.append(part)

        return f"({', '.join(parts)})"

    def get_return_annotation(self, item: dict[str, Any]) -> str:
        """Get the return type annotation."""
        return item.get("return_annotation", "")

    def render_module(
        self, item: dict[str, Any], children: list[dict[str, Any]], rel_dir: str
    ) -> str:
        """Render a module/package index page."""
        full_name = item.get("full_name", "")
        docstring = item.get("doc", "")
        parsed = self.parse_docstring(docstring)

        sections: list[str] = []
        frontmatter = make_frontmatter(full_name, self.pagination)
        sections.append(frontmatter)

        if self.include_module_docstring and docstring:
            body = self.render_docstring_body(parsed)
            if body:
                sections.append(body)

        # Group children by kind
        classes = [c for c in children if c.get("type") in ("class",)]
        functions = [c for c in children if c.get("type") in ("function",)]
        exceptions = [c for c in children if c.get("type") in ("exception",)]
        data_items = [c for c in children if c.get("type") in ("data", "attribute")]

        if classes:
            sections.append("## Classes\n")
            header = "| Class | Description |"
            sep = "|-------|-------------|"
            rows = []
            for cls in classes:
                name = cls["full_name"].rsplit(".", 1)[-1]
                desc = short_description(cls.get("doc"))
                link = f"[`{name}`](./classes/{slugify(name)}/)"
                rows.append(f"| {link} | {desc} |")
            sections.append("\n".join([header, sep] + rows))

        if functions:
            sections.append("## Functions\n")
            header = "| Function | Description |"
            sep = "|----------|-------------|"
            rows = []
            for fn in functions:
                name = fn["full_name"].rsplit(".", 1)[-1]
                desc = short_description(fn.get("doc"))
                link = f"[`{name}()`](./functions/{slugify(name)}/)"
                rows.append(f"| {link} | {desc} |")
            sections.append("\n".join([header, sep] + rows))

        if exceptions:
            sections.append("## Exceptions\n")
            header = "| Exception | Description |"
            sep = "|-----------|-------------|"
            rows = []
            for exc in exceptions:
                name = exc["full_name"].rsplit(".", 1)[-1]
                desc = short_description(exc.get("doc"))
                link = f"[`{name}`](./exceptions/{slugify(name)}/)"
                rows.append(f"| {link} | {desc} |")
            sections.append("\n".join([header, sep] + rows))

        if data_items:
            sections.append("## Data\n")
            header = "| Name | Type | Description |"
            sep = "|------|------|-------------|"
            rows = []
            for d in data_items:
                name = d["full_name"].rsplit(".", 1)[-1]
                type_str = format_type(d.get("annotation", ""))
                desc = short_description(d.get("doc"))
                link = f"[`{name}`](./data/{slugify(name)}/)"
                rows.append(f"| {link} | {type_str} | {desc} |")
            sections.append("\n".join([header, sep] + rows))

        return "\n\n".join(sections) + "\n"

    def render_class(self, item: dict[str, Any], members: list[dict[str, Any]]) -> str:
        """Render a class page."""
        full_name = item.get("full_name", "")
        short_name = full_name.rsplit(".", 1)[-1]
        docstring = item.get("doc", "")
        parsed = self.parse_docstring(docstring)
        bases = item.get("bases", [])

        sections: list[str] = []
        frontmatter = make_frontmatter(short_name, self.pagination)
        sections.append(frontmatter)

        # Class signature
        init_item = None
        for m in members:
            m_name = m.get("full_name", "").rsplit(".", 1)[-1]
            if m_name == "__init__" and m.get("type") == "method":
                init_item = m
                break

        sig = self.get_signature(init_item) if init_item else "()"
        sections.append(f"**`class {full_name}{sig}`**")

        if bases:
            base_links = [f"`{b}`" for b in bases]
            sections.append(f"**Bases:** {', '.join(base_links)}")

        body = self.render_docstring_body(parsed)
        if body:
            sections.append(body)

        dep = self.render_deprecation(parsed)
        if dep:
            sections.append(dep)

        # Constructor
        if init_item and self.include_init:
            init_parsed = self.parse_docstring(init_item.get("doc", ""))
            init_args = init_item.get("args", [])
            sections.append("## Constructor")
            sections.append(f"```python\n{short_name}{sig}\n```")
            param_table = build_param_table(init_parsed, init_args)
            if param_table:
                sections.append(param_table)

        # Methods
        methods = [
            m for m in members
            if m.get("type") == "method"
            and m.get("full_name", "").rsplit(".", 1)[-1] != "__init__"
            and not self.should_skip(m)
        ]
        if methods:
            sections.append("## Methods")
            for method in methods:
                method_name = method["full_name"].rsplit(".", 1)[-1]
                method_doc = method.get("doc", "")
                method_parsed = self.parse_docstring(method_doc)
                method_sig = self.get_signature(method)
                ret_ann = self.get_return_annotation(method)
                is_async = method.get("is_async", False)

                prefix = "async " if is_async else ""
                ret_str = f" -> {ret_ann}" if ret_ann else ""

                sections.append(f"### {method_name}")
                sections.append(
                    f"```python\n{prefix}def {method_name}{method_sig}{ret_str}\n```"
                )

                method_body = self.render_docstring_body(method_parsed)
                if method_body:
                    sections.append(method_body)

                param_table = build_param_table(method_parsed, method.get("args", []))
                if param_table:
                    sections.append(param_table)

                returns = self.render_returns(method_parsed)
                if returns:
                    sections.append(returns)

                raises = self.render_raises(method_parsed)
                if raises:
                    sections.append(raises)

        # Properties
        properties = [
            m for m in members
            if m.get("type") == "property" and not self.should_skip(m)
        ]
        if properties:
            sections.append("## Properties")
            for prop in properties:
                prop_name = prop["full_name"].rsplit(".", 1)[-1]
                prop_doc = prop.get("doc", "")
                prop_parsed = self.parse_docstring(prop_doc)
                prop_type = prop.get("annotation", "")

                sections.append(f"### {prop_name}")
                type_str = f"\n**Type:** `{prop_type}`" if prop_type else ""
                if type_str:
                    sections.append(type_str.strip())

                prop_body = self.render_docstring_body(prop_parsed)
                if prop_body:
                    sections.append(prop_body)

        # Class attributes
        attributes = [
            m for m in members
            if m.get("type") in ("data", "attribute") and not self.should_skip(m)
        ]
        if attributes:
            sections.append("## Class Attributes")
            for attr in attributes:
                attr_name = attr["full_name"].rsplit(".", 1)[-1]
                attr_doc = attr.get("doc", "")
                attr_parsed = self.parse_docstring(attr_doc)
                attr_type = attr.get("annotation", "")
                attr_value = attr.get("value", "")

                sections.append(f"### {attr_name}")
                type_val = ""
                if attr_type and attr_value:
                    type_val = f"**Type:** `{attr_type}` = `{attr_value}`"
                elif attr_type:
                    type_val = f"**Type:** `{attr_type}`"
                elif attr_value:
                    type_val = f"**Value:** `{attr_value}`"
                if type_val:
                    sections.append(type_val)

                attr_body = self.render_docstring_body(attr_parsed)
                if attr_body:
                    sections.append(attr_body)

        return "\n\n".join(sections) + "\n"

    def render_function(self, item: dict[str, Any]) -> str:
        """Render a function page."""
        full_name = item.get("full_name", "")
        short_name = full_name.rsplit(".", 1)[-1]
        docstring = item.get("doc", "")
        parsed = self.parse_docstring(docstring)
        sig = self.get_signature(item)
        ret_ann = self.get_return_annotation(item)
        is_async = item.get("is_async", False)

        sections: list[str] = []
        frontmatter = make_frontmatter(short_name, self.pagination)
        sections.append(frontmatter)

        prefix = "async " if is_async else ""
        ret_str = f" \u2192 {ret_ann}" if ret_ann else ""
        sections.append(f"**`{full_name}{sig}{ret_str}`**")

        body = self.render_docstring_body(parsed)
        if body:
            sections.append(body)

        dep = self.render_deprecation(parsed)
        if dep:
            sections.append(dep)

        param_table = build_param_table(parsed, item.get("args", []))
        if param_table:
            sections.append(param_table)

        returns = self.render_returns(parsed)
        if returns:
            sections.append(returns)

        raises = self.render_raises(parsed)
        if raises:
            sections.append(raises)

        examples = self.render_examples(parsed)
        if examples:
            sections.append(examples)

        return "\n\n".join(sections) + "\n"

    def render_data(self, item: dict[str, Any]) -> str:
        """Render a data/constant page."""
        full_name = item.get("full_name", "")
        short_name = full_name.rsplit(".", 1)[-1]
        docstring = item.get("doc", "")
        parsed = self.parse_docstring(docstring)
        annotation = item.get("annotation", "")
        value = item.get("value", "")

        sections: list[str] = []
        frontmatter = make_frontmatter(short_name, self.pagination)
        sections.append(frontmatter)

        type_val = ""
        if annotation and value:
            type_val = f"**Type:** `{annotation}` = `{value}`"
        elif annotation:
            type_val = f"**Type:** `{annotation}`"
        elif value:
            type_val = f"**Value:** `{value}`"

        sections.append(f"## {short_name}")
        if type_val:
            sections.append(type_val)

        body = self.render_docstring_body(parsed)
        if body:
            sections.append(body)

        return "\n\n".join(sections) + "\n"

    def render_exception(self, item: dict[str, Any], members: list[dict[str, Any]]) -> str:
        """Render an exception class page (same as class, with a note)."""
        content = self.render_class(item, members)
        # Add note after frontmatter
        parts = content.split("---\n", 2)
        if len(parts) >= 3:
            return f"{parts[0]}---\n{parts[1]}---\n\n:::note\nThis is an exception class.\n:::\n{parts[2]}"
        return content

    def write_file(self, rel_path: str, content: str) -> None:
        """Write a markdown file to the output directory."""
        file_path = self.output_dir / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        self.files.append(str(file_path))

    def register_definition(self, qualified_name: str, rel_url: str) -> None:
        """Register a definition mapping."""
        self.definitions[qualified_name] = rel_url

    def process_package(
        self, pkg_config: dict[str, Any], multi_package: bool
    ) -> "SphinxStructure":
        """Process a single Python package and generate all markdown files."""
        pkg_path = Path(pkg_config["path"]).resolve()
        module_name = pkg_config.get("module") or pkg_path.name

        if not pkg_path.exists():
            print(f"Error: Package path does not exist: {pkg_path}", file=sys.stderr)
            sys.exit(1)

        # Run autodoc2 analysis
        try:
            records = list(analyse_module(pkg_path, module_name))
        except Exception as e:
            print(f"Error analyzing package '{module_name}': {e}", file=sys.stderr)
            sys.exit(1)

        if not records:
            return SphinxStructure(
                name=module_name,
                kind="package",
                qualified_name=module_name,
                children=[],
                groups=[],
            )

        # Build database
        self.db.add(records)

        # Determine output subdirectory
        rel_base = module_name if multi_package else ""

        # Build structure tree and generate files
        root_items = [r for r in records if r.get("full_name") == module_name]
        root_item = root_items[0] if root_items else {"full_name": module_name, "type": "package", "doc": ""}

        return self._process_module(root_item, records, rel_base)

    def _process_module(
        self, item: dict[str, Any], all_records: list[dict[str, Any]], rel_dir: str
    ) -> "SphinxStructure":
        """Recursively process a module/package."""
        full_name = item.get("full_name", "")
        short_name = full_name.rsplit(".", 1)[-1] if "." in full_name else full_name
        item_type = item.get("type", "module")
        kind = "package" if item_type == "package" else "module"

        # Find direct children
        children = [
            r for r in all_records
            if r.get("full_name", "").rsplit(".", 1)[0] == full_name
            and r.get("full_name") != full_name
        ]

        # Filter hidden objects
        children = [c for c in children if not self.should_skip(c)]

        # Categorize children
        submodules = [c for c in children if c.get("type") in ("module", "package")]
        classes = [c for c in children if c.get("type") == "class"]
        functions = [c for c in children if c.get("type") == "function"]
        exceptions = [c for c in children if c.get("type") == "exception"]
        data_items = [c for c in children if c.get("type") in ("data", "attribute")]

        # Generate module index page
        module_content = self.render_module(item, children, rel_dir)
        index_path = f"{rel_dir}/index.md" if rel_dir else "index.md"
        self.write_file(index_path, module_content)
        self.register_definition(full_name, index_path)

        # Generate pages for each object kind
        groups: list[SphinxGroup] = []
        child_structures: list[SphinxStructure] = []

        # Classes
        if classes:
            group_children: list[SphinxGroupChild] = []
            for cls in classes:
                cls_name = cls["full_name"].rsplit(".", 1)[-1]
                cls_slug = slugify(cls_name)
                cls_dir = f"{rel_dir}/classes" if rel_dir else "classes"
                cls_path = f"{cls_dir}/{cls_slug}.md"

                # Find class members
                cls_members = [
                    r for r in all_records
                    if r.get("full_name", "").startswith(cls["full_name"] + ".")
                    and r.get("full_name", "").count(".") == cls["full_name"].count(".") + 1
                ]

                content = self.render_class(cls, cls_members)
                self.write_file(cls_path, content)
                self.register_definition(cls["full_name"], cls_path)

                # Register member definitions
                for member in cls_members:
                    member_name = member["full_name"].rsplit(".", 1)[-1]
                    self.register_definition(
                        member["full_name"],
                        f"{cls_path}#{slugify(member_name)}",
                    )

                group_children.append(
                    SphinxGroupChild(
                        name=cls_name,
                        qualified_name=cls["full_name"],
                        kind="class",
                    )
                )
            groups.append(SphinxGroup(title="Classes", children=group_children))

        # Functions
        if functions:
            group_children = []
            for fn in functions:
                fn_name = fn["full_name"].rsplit(".", 1)[-1]
                fn_slug = slugify(fn_name)
                fn_dir = f"{rel_dir}/functions" if rel_dir else "functions"
                fn_path = f"{fn_dir}/{fn_slug}.md"

                content = self.render_function(fn)
                self.write_file(fn_path, content)
                self.register_definition(fn["full_name"], fn_path)

                group_children.append(
                    SphinxGroupChild(
                        name=fn_name,
                        qualified_name=fn["full_name"],
                        kind="function",
                    )
                )
            groups.append(SphinxGroup(title="Functions", children=group_children))

        # Exceptions
        if exceptions:
            group_children = []
            for exc in exceptions:
                exc_name = exc["full_name"].rsplit(".", 1)[-1]
                exc_slug = slugify(exc_name)
                exc_dir = f"{rel_dir}/exceptions" if rel_dir else "exceptions"
                exc_path = f"{exc_dir}/{exc_slug}.md"

                exc_members = [
                    r for r in all_records
                    if r.get("full_name", "").startswith(exc["full_name"] + ".")
                    and r.get("full_name", "").count(".") == exc["full_name"].count(".") + 1
                ]

                content = self.render_exception(exc, exc_members)
                self.write_file(exc_path, content)
                self.register_definition(exc["full_name"], exc_path)

                group_children.append(
                    SphinxGroupChild(
                        name=exc_name,
                        qualified_name=exc["full_name"],
                        kind="exception",
                    )
                )
            groups.append(SphinxGroup(title="Exceptions", children=group_children))

        # Data
        if data_items:
            group_children = []
            for d in data_items:
                d_name = d["full_name"].rsplit(".", 1)[-1]
                d_slug = slugify(d_name)
                d_dir = f"{rel_dir}/data" if rel_dir else "data"
                d_path = f"{d_dir}/{d_slug}.md"

                content = self.render_data(d)
                self.write_file(d_path, content)
                self.register_definition(d["full_name"], d_path)

                group_children.append(
                    SphinxGroupChild(
                        name=d_name,
                        qualified_name=d["full_name"],
                        kind="data",
                    )
                )
            groups.append(SphinxGroup(title="Data", children=group_children))

        # Submodules (recursive)
        if submodules:
            submod_group_children: list[SphinxGroupChild] = []
            for submod in submodules:
                submod_name = submod["full_name"].rsplit(".", 1)[-1]
                submod_dir = f"{rel_dir}/{submod_name}" if rel_dir else submod_name
                child_struct = self._process_module(submod, all_records, submod_dir)
                child_structures.append(child_struct)
                submod_group_children.append(
                    SphinxGroupChild(
                        name=submod_name,
                        qualified_name=submod["full_name"],
                        kind=child_struct.kind,
                    )
                )
            if submod_group_children:
                groups.append(
                    SphinxGroup(title="Modules", children=submod_group_children)
                )

        return SphinxStructure(
            name=short_name,
            kind=kind,
            qualified_name=full_name,
            children=child_structures if child_structures else None,
            groups=groups if groups else None,
        )


# ---------------------------------------------------------------------------
# Data classes for structure output
# ---------------------------------------------------------------------------


class SphinxGroupChild:
    def __init__(self, name: str, qualified_name: str, kind: str):
        self.name = name
        self.qualified_name = qualified_name
        self.kind = kind

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "qualifiedName": self.qualified_name,
            "kind": self.kind,
        }


class SphinxGroup:
    def __init__(self, title: str, children: list[SphinxGroupChild]):
        self.title = title
        self.children = children

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "children": [c.to_dict() for c in self.children],
        }


class SphinxStructure:
    def __init__(
        self,
        name: str,
        kind: str,
        qualified_name: str,
        children: list["SphinxStructure"] | None = None,
        groups: list[SphinxGroup] | None = None,
    ):
        self.name = name
        self.kind = kind
        self.qualified_name = qualified_name
        self.children = children
        self.groups = groups

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "kind": self.kind,
            "qualifiedName": self.qualified_name,
        }
        if self.children:
            result["children"] = [c.to_dict() for c in self.children]
        if self.groups:
            result["groups"] = [g.to_dict() for g in self.groups]
        return result


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Starlight-Sphinx Python renderer")
    parser.add_argument(
        "--packages",
        required=True,
        help='JSON array of package configs, e.g. [{"path": "./mypackage"}]',
    )
    parser.add_argument(
        "--output", required=True, help="Output directory for generated Markdown files"
    )
    parser.add_argument(
        "--config", default="{}", help="JSON object with rendering configuration"
    )
    parser.add_argument(
        "--pagination",
        action="store_true",
        default=False,
        help="Enable pagination links",
    )
    parser.add_argument(
        "--base-url", default="/api/", help="Base URL for generated docs"
    )
    args = parser.parse_args()

    packages = json.loads(args.packages)
    config = json.loads(args.config)
    output_dir = Path(args.output).resolve()
    multi_package = len(packages) > 1

    # Clean output directory
    if output_dir.exists():
        import shutil
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    db = InMemoryDb()
    renderer = MarkdownRenderer(
        db=db,
        output_dir=output_dir,
        base_url=args.base_url,
        pagination=args.pagination,
        config=config,
    )

    # Process all packages
    structures: list[SphinxStructure] = []
    for pkg in packages:
        if isinstance(pkg, str):
            pkg = {"path": pkg}
        structure = renderer.process_package(pkg, multi_package)
        structures.append(structure)

    # Build final structure
    if len(structures) == 1:
        final_structure = structures[0]
    else:
        final_structure = SphinxStructure(
            name="API",
            kind="package",
            qualified_name="",
            children=structures,
            groups=None,
        )

    # Output manifest to stdout
    manifest = {
        "structure": final_structure.to_dict(),
        "definitions": renderer.definitions,
        "files": renderer.files,
    }
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
