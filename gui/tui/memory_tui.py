#!/usr/bin/env python3
"""Memory TUI — full-screen Textual dashboard for wt-memory."""

import json
import subprocess
import sys
from datetime import datetime

try:
    from textual.app import App, ComposeResult
except ImportError:
    print("Error: 'textual' package is required. Install it: pip install textual", file=sys.stderr)
    sys.exit(1)
from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.widgets import Footer, Header, Static


# ─── Data layer ──────────────────────────────────────────────────────


class MemoryDataReader:
    """Reads metrics and memory stats for the dashboard."""

    def __init__(self, wt_tools_root, project=None):
        self.wt_tools_root = wt_tools_root
        self.project = project

    def read_metrics(self, since_days=7):
        """Import query_report directly via sys.path."""
        try:
            from lib.metrics import query_report
            return query_report(since_days=since_days, project=self.project)
        except Exception:
            return None

    def read_stats(self):
        """Call wt-memory stats --json via subprocess."""
        try:
            cmd = ["wt-memory", "stats", "--json"]
            if self.project:
                cmd = ["wt-memory", "--project", self.project, "stats", "--json"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return json.loads(result.stdout)
        except Exception:
            pass
        return None

    def is_metrics_enabled(self):
        try:
            from lib.metrics import is_enabled
            return is_enabled()
        except Exception:
            return False


# ─── Rendering ───────────────────────────────────────────────────────


def _fmt_count(n):
    """Format large numbers compactly: 16932 -> 16.9K"""
    if n >= 10000:
        return f"{n / 1000:.1f}K"
    if n >= 1000:
        return f"{n:,}"
    return str(n)


def _sparkline(values):
    """Build a sparkline string from numeric values."""
    if not values:
        return ""
    mn, mx = min(values), max(values)
    rng = mx - mn if mx > mn else 1
    chars = " ▁▂▃▄▅▆▇█"
    return "".join(chars[min(8, int((v - mn) / rng * 8))] for v in values)


def _render_bar(items, bar_max=30):
    """Render a horizontal bar chart. items: list of (label, value, total, color)."""
    lines = []
    for label, val, total, clr in items:
        if val == 0:
            continue
        pct = val / total * 100
        bar_len = int(pct / 100 * bar_max)
        filled = "\u2588" * bar_len
        dots = "\u00b7" * (bar_max - bar_len)
        lines.append(f"  {label:<7} [{clr}]{filled}[/]{dots} {pct:>4.0f}%")
    return lines


def render_content(report, mem_stats, project, since_days, metrics_enabled=True):
    """Render the full dashboard as a Rich Table with 2 columns."""
    from rich.table import Table
    from rich.text import Text

    now = datetime.now().strftime("%H:%M:%S")
    proj_label = project if project else "all projects"

    # ── Build LEFT column ──
    left = []

    # DATABASE
    left.append("[bold blue]DATABASE[/]")
    if mem_stats:
        total = mem_stats.get("total", mem_stats.get("total_memories", 0))
        noise_raw = mem_stats.get("noise_ratio", 0)
        try:
            noise_val = float(noise_raw) if not isinstance(noise_raw, str) else float(noise_raw.rstrip("%"))
        except (ValueError, TypeError):
            noise_val = 0
        noise_color = "green" if noise_val < 15 else ("yellow" if noise_val < 30 else "red")
        types = mem_stats.get("type_distribution", {})
        t_l = types.get("Learning", 0)
        t_c = types.get("Context", 0)
        t_d = types.get("Decision", 0)
        left.append(
            f"  [bold]{total}[/] memories  [{noise_color}]{noise_val:.0f}%[/] noise"
        )
        left.append(f"  [green]L:{t_l}[/]  [blue]C:{t_c}[/]  [magenta]D:{t_d}[/]")
    else:
        left.append("  [dim]Memory DB: unavailable[/]")

    # HOOK OVERHEAD
    if not report:
        if not metrics_enabled:
            left.append("[yellow]No metrics[/]")
            left.append("[yellow]Enable: wt-memory metrics --enable[/]")
        else:
            left.append("[dim]No metrics data yet.[/]")
        # Return early — single-column fallback
        table = Table(
            show_header=False, show_edge=False, pad_edge=False,
            box=None, expand=True,
        )
        table.add_column(ratio=1)
        table.add_row("\n".join(left))
        return table

    left.append("[bold blue]HOOK OVERHEAD[/]")
    sessions_cnt = report["session_count"]
    injections = report["total_injections"]
    tokens = report["total_tokens"]
    avg_tok = tokens / sessions_cnt if sessions_cnt > 0 else 0
    budget_pct = avg_tok / 200000 * 100
    budget_color = "green" if budget_pct < 3 else ("yellow" if budget_pct < 5 else "red")
    left.append(
        f"  [bold]{sessions_cnt}[/] sess  [bold]{_fmt_count(injections)}[/] inj"
        f"  [bold]{_fmt_count(tokens)}[/] tok"
    )
    left.append(f"  Avg: {avg_tok:,.0f}/s  Budget: [{budget_color}]{budget_pct:.2f}%[/]")
    # LAYERS
    layers = report.get("layers", [])
    if layers:
        left.append("[bold blue]LAYERS[/]")
        left.append("  [dim]Name       Cnt  AvgTok AvgRel[/]")
        for layer in layers:
            avg_rel = layer.get("avg_rel", 0)
            rel_color = "green" if avg_rel >= 0.5 else ("yellow" if avg_rel >= 0.3 else ("red" if avg_rel > 0 else "dim"))
            left.append(
                f"  [cyan]{layer['layer']:<10}[/] {_fmt_count(layer['cnt']):>4}x"
                f" {layer['avg_tok']:>5.0f}"
                f"  [{rel_color}]{avg_rel:.2f}[/]"
            )
    # USAGE SIGNALS (2-column compact)
    left.append("[bold blue]USAGE SIGNALS[/]")
    usage_rate = report.get("usage_rate")
    inj_ids = report.get("total_injected_ids", 0)
    mat_ids = report.get("total_matched_ids", 0)
    if usage_rate is not None:
        u_color = "green" if usage_rate >= 30 else ("yellow" if usage_rate >= 10 else "red")
        usage_str = f"Use [{u_color}][bold]{usage_rate:.0f}%[/][/]({mat_ids}/{inj_ids})"
    else:
        usage_str = "Use [dim]N/A[/]"
    cite_rate = report["citation_rate"]
    c_color = "green" if cite_rate >= 2 else ("yellow" if cite_rate >= 0.5 else "dim")
    dedup_rate = report["dedup_rate"]
    d_color = "green" if dedup_rate >= 10 else "dim"
    empty_rate = report["empty_rate"]
    e_color = "green" if empty_rate < 5 else ("yellow" if empty_rate < 15 else "red")
    left.append(f"  {usage_str}  Cite [{c_color}]{cite_rate:.1f}%[/]({report['total_citations']})")
    left.append(f"  Dup [{d_color}]{dedup_rate:.1f}%[/]({report['dedup_hits']})  Emp [{e_color}]{empty_rate:.1f}%[/]({report['empty_count']})")

    # ── Build RIGHT column ──
    right = []

    # RELEVANCE
    rel = report.get("relevance", {})
    total_rel = rel.get("strong", 0) + rel.get("partial", 0) + rel.get("weak", 0)
    if total_rel > 0:
        right.append("[bold blue]RELEVANCE[/]")
        right.extend(_render_bar([
            ("strong", rel.get("strong", 0), total_rel, "green"),
            ("partial", rel.get("partial", 0), total_rel, "yellow"),
            ("weak", rel.get("weak", 0), total_rel, "red"),
        ]))
    # IMPORTANCE (count before bar)
    if mem_stats:
        imp = mem_stats.get("importance_histogram", {})
        imp_total = sum(imp.values())
        if imp_total > 0:
            right.append("[bold blue]IMPORTANCE[/]")
            bar_max = 20
            for label, key, clr in [
                ("low", "0.0-0.2", "red"),
                ("mid-lo", "0.2-0.4", "yellow"),
                ("mid-hi", "0.4-0.6", "green"),
                ("high", "0.6-0.8", "cyan"),
                ("top", "0.8-1.0", "magenta"),
            ]:
                val = imp.get(key, 0)
                if val == 0:
                    continue
                pct = val / imp_total * 100
                bar_len = int(pct / 100 * bar_max)
                filled = "\u2588" * bar_len
                dots = "\u00b7" * (bar_max - bar_len)
                right.append(f"  {label:<6} [dim]{val:>3}[/] [{clr}]{filled}[/]{dots} {pct:.0f}%")
    # SPARKLINES
    daily_tokens = report.get("daily_tokens", [])
    daily_relevance = report.get("daily_relevance", [])
    if len(daily_tokens) >= 3:
        right.append("[bold blue]DAILY TREND[/]")
        tok_values = [d["tokens"] for d in daily_tokens]
        tok_spark = _sparkline(tok_values)
        right.append(f"  tok [cyan]{tok_spark}[/]")
        right.append(f"      [dim]{_fmt_count(min(tok_values))}\u2014{_fmt_count(max(tok_values))}[/]")
        if daily_relevance:
            rel_values = [d["avg_relevance"] for d in daily_relevance]
            rel_spark = _sparkline(rel_values)
            right.append(f"  rel [green]{rel_spark}[/]")
            right.append(f"      [dim]{min(rel_values):.3f}\u2014{max(rel_values):.3f}[/]")
    # HOT TAGS
    if mem_stats:
        tags = mem_stats.get("tag_distribution", mem_stats.get("top_tags", {}))
        if tags:
            skip_prefixes = ("source:", "branch:", "phase:")
            interesting = [(k, v) for k, v in tags.items() if not any(k.startswith(p) for p in skip_prefixes)]
            if interesting:
                right.append("[bold blue]HOT TAGS[/]")
                for k, v in interesting[:8]:
                    short_k = k if len(k) <= 35 else k[:33] + ".."
                    right.append(f"  [dim]{v:>4}[/]  {short_k}")

    # ── Assemble 2-column table ──
    table = Table(
        title=f"[bold]{proj_label}[/]  [dim]{since_days}d \u00b7 {now}[/]",
        show_header=False, show_edge=True, pad_edge=True,
        border_style="cyan", expand=True,
    )
    table.add_column(ratio=1)
    table.add_column(ratio=1)
    table.add_row("\n".join(left), "\n".join(right))
    return table


# ─── App ─────────────────────────────────────────────────────────────


CSS = """
#dashboard {
    padding: 1 2;
}
"""


class MemoryTUI(App):
    """Full-screen Textual dashboard for wt-memory."""

    TITLE = "wt-memory"
    CSS = CSS

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
    ]

    def __init__(self, reader, since_days=7):
        super().__init__()
        self.reader = reader
        self.since_days = since_days

    def compose(self) -> ComposeResult:
        yield Header()
        with ScrollableContainer():
            yield Static("Loading...", id="dashboard")
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = self.reader.project or "all projects"
        self._refresh_data()
        self.set_interval(10.0, self._refresh_data)

    def _refresh_data(self) -> None:
        report = self.reader.read_metrics(since_days=self.since_days)
        mem_stats = self.reader.read_stats()
        enabled = self.reader.is_metrics_enabled()
        content = render_content(
            report, mem_stats, self.reader.project, self.since_days, enabled
        )
        self.query_one("#dashboard", Static).update(content)

    def action_refresh(self) -> None:
        self._refresh_data()
        self.notify("Refreshed", timeout=1)


# ─── Entry point ─────────────────────────────────────────────────────


def main():
    if len(sys.argv) < 2:
        print("Usage: memory_tui.py <wt_tools_root> [project] [since_days]", file=sys.stderr)
        sys.exit(1)

    wt_tools_root = sys.argv[1]
    project = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
    since_days = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else 7

    # Insert wt-tools root into sys.path for lib.metrics import
    if wt_tools_root not in sys.path:
        sys.path.insert(0, wt_tools_root)

    reader = MemoryDataReader(wt_tools_root, project)
    app = MemoryTUI(reader, since_days)
    app.run()


if __name__ == "__main__":
    main()
