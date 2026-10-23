"""
Renderers for Trailhead:
- render_markdown: human-readable CLI markdown output
- render_trail_svg: self-contained radial dependency visualization SVG (no external JS/CDNs)
"""
import html
import math
from typing import Dict, List, Set
import xml.etree.ElementTree as ET

from trailhead.models import Trail

def render_markdown(trail: Trail) -> str:
    """Format Trail as clear GitHub-flavored markdown."""
    lines: List[str] = [
        "# Trailhead Contribution Trail",
        "",
        f"**Status**: `{trail.status}` | **Confidence**: `{trail.confidence.upper()}` | **Offline Violations**: `{trail.netguard.get('blocked_attempts', 0)}`",
    ]

    if trail.banner:
        lines.extend(["", f"> [!NOTE]", f"> {trail.banner}", ""])

    if trail.status == "low_confidence":
        lines.extend([
            "## Exploration Areas (Low Confidence)",
            "The issue text is broad or ambiguous. Explore these component modules first:",
            "",
        ])
        for area in trail.explore_areas:
            lines.append(f"- `{area}`")
        if trail.clarifying_question:
            lines.extend([
                "",
                "### Suggested Question for Maintainers:",
                f"> \"{trail.clarifying_question}\"",
                "",
            ])

    # Edit Targets
    lines.extend(["", "## Edit Here (Candidate Fix Locations)", ""])
    if not trail.edit:
        lines.append("*No edit candidates identified.*")
    for p in trail.edit:
        loc = f"`{p.file}:{p.start}-{p.end}`" if p.start and p.end else f"`{p.file}` (file-level)"
        lines.append(f"### {p.alias}: `{p.node_id}` ({loc})")
        lines.append(f"**Why**: {p.why}")
        if p.snippet:
            lines.extend(["```python", p.snippet.strip(), "```", ""])

    # Read First Context
    if trail.read_first:
        lines.extend(["## Read First (Required Context)", ""])
        for p in trail.read_first:
            loc = f"`{p.file}:{p.start}-{p.end}`" if p.start and p.end else f"`{p.file}`"
            lines.append(f"- **{p.alias}**: `{p.node_id}` ({loc}) — *{p.why}*")
        lines.append("")

    # Blast Radius
    if trail.blast:
        lines.extend(["## Blast Radius & Inbound Impact", ""])
        for b in trail.blast:
            risk = b.get("risk", "low").upper()
            target = b.get("target", "")
            count = b.get("total_count", 0)
            callers = ", ".join(f"`{c}`" for c in b.get("callers", [])[:5]) or "None"
            lines.append(f"- **{target}**: **{count} callers** [Risk: `{risk}`]")
            lines.append(f"  - Direct callers: {callers}")
        lines.append("")

    # Tests to run
    lines.extend(["## Tests to Run", ""])
    if trail.tests:
        lines.append("Copy and run this command:")
        cmd = f"pytest {' '.join(trail.tests[:5])}"
        lines.extend([f"```bash", cmd, "```", ""])
        for t in trail.tests:
            lines.append(f"- `{t}`")
    else:
        lines.append("`pytest` (run standard suite)")
    lines.append("")

    # PR Checklist
    if trail.checklist:
        lines.extend(["## Before You Open the PR", ""])
        for item in trail.checklist:
            lines.append(f"- [ ] {item}")
        lines.append("")

    # Execution Trace Summary
    lines.extend([
        "## Local Execution Trace",
        f"- Total tool calls: `{len(trail.trace)}`",
        f"- Overall time: `{trail.timing.get('total_s', 0.0)}s`",
        f"- Local Model: `{trail.model.get('name', 'none')}` ({trail.model.get('mode', 'offline')})",
        "",
    ])

    return "\n".join(lines)

def render_trail_svg(trail: Trail, width: int = 800, height: int = 560) -> str:
    """
    Generate clean, standalone radial SVG dependency graph visualizing top picks, callers, and callees.
    Zero external JS libraries; strictly valid XML.
    """
    all_picks = trail.edit + trail.read_first
    if not all_picks:
        # Fallback empty SVG
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            f'<rect width="100%" height="100%" fill="#12151c"/>'
            f'<text x="50%" y="50%" fill="#8892b0" font-family="system-ui, sans-serif" font-size="16" text-anchor="middle">No candidate nodes to display</text>'
            f'</svg>'
        )

    cx, cy = width / 2.0, height / 2.0
    inner_radius = 120.0
    outer_radius = 210.0

    lines_svg: List[str] = []
    nodes_svg: List[str] = []

    # Map candidate picks to inner ring positions
    n_picks = len(all_picks)
    pick_positions: Dict[str, tuple[float, float]] = {}

    for i, p in enumerate(all_picks):
        angle = (2.0 * math.pi * i) / max(n_picks, 1) - (math.pi / 2.0)
        px = cx + inner_radius * math.cos(angle)
        py = cy + inner_radius * math.sin(angle)
        pick_positions[p.node_id] = (px, py)

        color = "#FF5722" if p.role == "edit" else "#03A9F4"
        stroke = "#FF8A65" if p.role == "edit" else "#81D4FA"
        label = html.escape(p.node_id.split("::")[-1] or p.alias)

        # Center pick node
        nodes_svg.append(
            f'<g class="node pick-node">'
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="22" fill="{color}" stroke="{stroke}" stroke-width="2.5" />'
            f'<text x="{px:.1f}" y="{py + 4:.1f}" fill="#ffffff" font-family="system-ui, sans-serif" font-size="11" font-weight="bold" text-anchor="middle">{p.alias}</text>'
            f'<text x="{px:.1f}" y="{py + 36:.1f}" fill="#e2e8f0" font-family="system-ui, sans-serif" font-size="10" text-anchor="middle">{label[:18]}</text>'
            f'</g>'
        )

    # Position outer caller/blast nodes
    seen_callers: Set[str] = set()
    caller_list: List[str] = []
    edges_to_draw: List[tuple[str, str]] = []

    for b in trail.blast:
        tgt = b.get("target", "")
        for c in b.get("callers", [])[:4]:
            if c not in seen_callers and c not in pick_positions:
                seen_callers.add(c)
                caller_list.append(c)
            edges_to_draw.append((c, tgt))

    n_callers = len(caller_list)
    caller_positions: Dict[str, tuple[float, float]] = {}

    for j, c_name in enumerate(caller_list):
        angle = (2.0 * math.pi * j) / max(n_callers, 1) - (math.pi / 2.0)
        ox = cx + outer_radius * math.cos(angle)
        oy = cy + outer_radius * math.sin(angle)
        caller_positions[c_name] = (ox, oy)
        label = html.escape(c_name.split("::")[-1])

        nodes_svg.append(
            f'<g class="node caller-node">'
            f'<circle cx="{ox:.1f}" cy="{oy:.1f}" r="15" fill="#2d3748" stroke="#4a5568" stroke-width="2" />'
            f'<text x="{ox:.1f}" y="{oy + 25:.1f}" fill="#a0aec0" font-family="system-ui, sans-serif" font-size="9" text-anchor="middle">{label[:14]}</text>'
            f'</g>'
        )

    # Draw connection lines
    for src, dst in edges_to_draw:
        p1 = caller_positions.get(src)
        p2 = pick_positions.get(dst)
        if p1 and p2:
            lines_svg.append(
                f'<line x1="{p1[0]:.1f}" y1="{p1[1]:.1f}" x2="{p2[0]:.1f}" y2="{p2[1]:.1f}" stroke="#4a5568" stroke-width="1.5" stroke-dasharray="3,3" />'
            )

    svg_content = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
        f'<rect width="100%" height="100%" fill="#0f172a" rx="10"/>\n'
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{inner_radius:.1f}" fill="none" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>\n'
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{outer_radius:.1f}" fill="none" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>\n'
        f'<g id="connections">\n' + "\n".join(lines_svg) + f'\n</g>\n'
        f'<g id="nodes">\n' + "\n".join(nodes_svg) + f'\n</g>\n'
        f'<text x="20" y="30" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="12" font-weight="600">Trailhead Dependency Trail</text>\n'
        f'<circle cx="28" cy="50" r="6" fill="#FF5722"/>\n'
        f'<text x="40" y="54" fill="#cbd5e1" font-family="system-ui, sans-serif" font-size="10">Edit Target</text>\n'
        f'<circle cx="110" cy="50" r="6" fill="#03A9F4"/>\n'
        f'<text x="122" y="54" fill="#cbd5e1" font-family="system-ui, sans-serif" font-size="10">Read First</text>\n'
        f'<circle cx="190" cy="50" r="6" fill="#2d3748"/>\n'
        f'<text x="202" y="54" fill="#cbd5e1" font-family="system-ui, sans-serif" font-size="10">Caller / Impact</text>\n'
        f'</svg>'
    )
    return svg_content
