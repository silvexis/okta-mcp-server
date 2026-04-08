"""Report generator for creating HTML and JSON test reports."""

import json
import html
from pathlib import Path
from datetime import datetime
from typing import List

from framework_poc.core.models import CheckResult, Judgment, Report


class ReportGenerator:
    """Generate test reports in multiple formats."""

    def generate(
        self,
        results: List[CheckResult],
        judgments: List[Judgment],
        tool_name: str
    ) -> Report:
        """
        Generate comprehensive report.

        Args:
            results: List of check results from deterministic tests
            judgments: List of judgments from non-deterministic tests
            tool_name: Name of the tool tested

        Returns:
            Report object
        """
        # Calculate summaries by layer
        layer_summaries = {}
        for layer in range(6):
            layer_results = [r for r in results if r.layer == layer]
            if layer_results or layer == 4:  # Include layer 4 even if empty
                total = len(layer_results)
                passed = sum(1 for r in layer_results if r.passed)
                failed = total - passed
                pass_rate = (passed / total * 100) if total > 0 else 0

                layer_summaries[layer] = {
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "pass_rate": pass_rate
                }

        # Add Layer 4 and Layer 5 judgments separately
        if judgments:
            # Layer 4 judgments (LLM Behavior)
            layer_4_judgments = [j for j in judgments if j.test_case and j.test_case.layer == 4]
            if layer_4_judgments:
                layer_4_passed = sum(1 for j in layer_4_judgments if j.passed)
                layer_summaries[4] = {
                    "total": len(layer_4_judgments),
                    "passed": layer_4_passed,
                    "failed": len(layer_4_judgments) - layer_4_passed,
                    "pass_rate": (layer_4_passed / len(layer_4_judgments) * 100)
                }

            # Layer 5 judgments (Destructive Ops Safety)
            layer_5_judgments = [j for j in judgments if j.test_case and j.test_case.layer == 5]
            if layer_5_judgments:
                layer_5_passed = sum(1 for j in layer_5_judgments if j.passed)
                layer_summaries[5] = {
                    "total": len(layer_5_judgments),
                    "passed": layer_5_passed,
                    "failed": len(layer_5_judgments) - layer_5_passed,
                    "pass_rate": (layer_5_passed / len(layer_5_judgments) * 100)
                }

        # Collect failures
        failures = [r for r in results if not r.passed]

        # Overall pass status (deterministic layers must all pass)
        overall_passed = len(failures) == 0

        return Report(
            tool_name=tool_name,
            timestamp=datetime.now().isoformat(),
            layer_summaries=layer_summaries,
            all_results=results,
            all_judgments=judgments,
            failures=failures,
            overall_passed=overall_passed
        )

    def export_html(self, report: Report, output_path: str):
        """
        Generate HTML report.

        Args:
            report: Report object
            output_path: Path to save HTML file
        """
        html = self._generate_html(report)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(html)

    def export_json(self, report: Report, output_path: str):
        """
        Generate JSON report.

        Args:
            report: Report object
            output_path: Path to save JSON file
        """
        data = report.to_dict()

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json.dumps(data, indent=2))

    def _generate_html(self, report: Report) -> str:
        """Generate HTML report content."""
        # Calculate overall stats
        total_tests = sum(s["total"] for s in report.layer_summaries.values())
        total_passed = sum(s["passed"] for s in report.layer_summaries.values())
        total_failed = sum(s["failed"] for s in report.layer_summaries.values())
        overall_pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MCP Test Report - {report.tool_name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
            scroll-behavior: smooth;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            margin-bottom: 10px;
        }}
        .summary {{
            background-color: #f9f9f9;
            padding: 20px;
            border-radius: 6px;
            margin-bottom: 30px;
        }}
        .summary-row {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
        }}
        .summary-label {{
            font-weight: 600;
            color: #666;
        }}
        .summary-value {{
            font-weight: 500;
        }}
        .pass {{
            color: #22c55e;
            font-weight: 600;
        }}
        .fail {{
            color: #ef4444;
            font-weight: 600;
        }}
        .stat {{
            padding: 10px 15px;
            background-color: #f9f9f9;
            border-radius: 4px;
        }}
        .stat-label {{
            font-size: 0.9em;
            color: #666;
        }}
        .stat-value {{
            font-size: 1.3em;
            font-weight: 600;
        }}
        .test-result {{
            padding: 10px;
            margin: 5px 0;
            border-left: 4px solid #e5e5e5;
            background-color: #fafafa;
        }}
        .test-result.passed {{
            border-left-color: #22c55e;
        }}
        .test-result.failed {{
            border-left-color: #ef4444;
        }}
        .test-name {{
            font-weight: 500;
            margin-bottom: 5px;
        }}
        .test-message {{
            color: #666;
            font-size: 0.9em;
        }}
        .test-time {{
            color: #999;
            font-size: 0.85em;
        }}
        .error {{
            background-color: #fef2f2;
            border: 1px solid #fecaca;
            padding: 10px;
            margin-top: 5px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 0.85em;
            color: #991b1b;
        }}
        .progress-bar {{
            width: 100%;
            height: 30px;
            background-color: #e5e5e5;
            border-radius: 4px;
            overflow: hidden;
            margin: 20px 0;
        }}
        .progress-fill {{
            height: 100%;
            background-color: #22c55e;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 600;
        }}
        .timestamp {{
            color: #999;
            font-size: 0.9em;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.85em;
            font-weight: 600;
        }}
        .badge.success {{
            background-color: #dcfce7;
            color: #166534;
        }}
        .badge.failure {{
            background-color: #fee2e2;
            color: #991b1b;
        }}
        /* Navigation bar */
        .nav {{
            position: sticky;
            top: 0;
            background-color: #1e293b;
            padding: 10px 20px;
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            z-index: 100;
            margin: -20px -20px 20px -20px;
            border-radius: 8px 8px 0 0;
        }}
        .nav-link {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            border-radius: 4px;
            color: #e2e8f0;
            text-decoration: none;
            font-size: 0.85em;
            font-weight: 500;
        }}
        .nav-link:hover {{
            background-color: #334155;
        }}
        .nav-link.pass {{ color: #86efac; }}
        .nav-link.fail {{ color: #fca5a5; }}
        .nav-link.skip {{ color: #94a3b8; }}
        /* Collapsible layers via <details> */
        .layer {{
            margin: 20px 0;
            border: 1px solid #e5e5e5;
            border-radius: 6px;
            overflow: hidden;
        }}
        .layer summary {{
            font-size: 1.15em;
            font-weight: 600;
            color: #333;
            padding: 16px 20px;
            cursor: pointer;
            list-style: none;
            display: flex;
            align-items: center;
            justify-content: space-between;
            background-color: #fafafa;
            border-bottom: 1px solid #e5e5e5;
        }}
        .layer summary::-webkit-details-marker {{ display: none; }}
        .layer summary::after {{
            content: '▼';
            font-size: 0.7em;
            color: #999;
            transition: transform 0.2s;
        }}
        .layer[open] summary::after {{
            transform: rotate(180deg);
        }}
        .layer-body {{
            padding: 20px;
        }}
        .layer-stats {{
            display: flex;
            gap: 20px;
            margin-bottom: 15px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>MCP E2E Test Report</h1>
        <p class="timestamp">Generated: {report.timestamp}</p>

        <div class="summary">
            <div class="summary-row">
                <span class="summary-label">Tool:</span>
                <span class="summary-value">{report.tool_name}</span>
            </div>
            <div class="summary-row">
                <span class="summary-label">Overall Status:</span>
                <span class="badge {'success' if report.overall_passed else 'failure'}">
                    {'PASSED' if report.overall_passed else 'FAILED'}
                </span>
            </div>
            <div class="summary-row">
                <span class="summary-label">Total Tests:</span>
                <span class="summary-value">{total_tests}</span>
            </div>
            <div class="summary-row">
                <span class="summary-label">Passed:</span>
                <span class="pass">{total_passed}</span>
            </div>
            <div class="summary-row">
                <span class="summary-label">Failed:</span>
                <span class="fail">{total_failed}</span>
            </div>

            <div class="progress-bar">
                <div class="progress-fill" style="width: {overall_pass_rate}%">
                    {overall_pass_rate:.1f}%
                </div>
            </div>
        </div>

        {self._render_nav_html(report)}

        {self._render_layers_html(report)}

        {self._render_failures_html(report) if (report.failures or any(not j.passed for j in report.all_judgments)) else ''}
    </div>
<script>
    // When a nav link is clicked: open the target <details> and smooth-scroll to it
    document.querySelectorAll('.nav-link[href^="#"]').forEach(function(link) {{
        link.addEventListener('click', function(e) {{
            e.preventDefault();
            var target = document.querySelector(this.getAttribute('href'));
            if (!target) return;
            if (target.tagName === 'DETAILS') target.open = true;
            target.scrollIntoView({{behavior: 'smooth', block: 'start'}});
        }});
    }});
</script>
</body>
</html>"""

        return html

    def _render_nav_html(self, report: Report) -> str:
        """Render a sticky navigation bar linking to each layer section."""
        layer_names = {
            0: "L0: Contract",
            1: "L1: Startup",
            2: "L2: Validation",
            3: "L3: Execution",
            4: "L4: LLM",
            5: "L5: Safety"
        }

        links = []
        for layer in sorted(report.layer_summaries.keys()):
            summary = report.layer_summaries[layer]
            # Convert layer key to int (layer summaries may have string keys from JSON)
            layer_int = int(layer) if isinstance(layer, str) else layer
            if summary["total"] == 0:
                css_class = "skip"
                label = f"{layer_names.get(layer_int, f'L{layer_int}')} (0)"
            elif summary["failed"] == 0:
                css_class = "pass"
                label = f"✓ {layer_names.get(layer_int, f'L{layer_int}')} {summary['passed']}/{summary['total']}"
            else:
                css_class = "fail"
                label = f"✗ {layer_names.get(layer_int, f'L{layer_int}')} {summary['passed']}/{summary['total']}"
            links.append(
                f'<a class="nav-link {css_class}" href="#layer-{layer_int}">{label}</a>'
            )

        if report.failures:
            links.append('<a class="nav-link fail" href="#failures">⚠ Failures</a>')

        return f'<nav class="nav">{"".join(links)}</nav>'

    def _render_layers_html(self, report: Report) -> str:
        """Render all layers in HTML."""
        layer_names = {
            0: "Layer 0: Contract Integrity",
            1: "Layer 1: Server Startup & Auth",
            2: "Layer 2: Input Validation",
            3: "Layer 3: Tool Execution",
            4: "Layer 4: LLM Behavior",
            5: "Layer 5: Destructive Ops Safety"
        }

        html_parts = []

        for layer in sorted(report.layer_summaries.keys()):
            summary = report.layer_summaries[layer]
            # Convert layer key to int for comparison (layer summaries may have string keys from JSON)
            layer_int = int(layer) if isinstance(layer, str) else layer
            layer_name = layer_names.get(layer_int, f"Layer {layer_int}")

            # Get results for this layer (compare as integers)
            layer_results = [r for r in report.all_results if r.layer == layer_int]

            # For Layers 4 and 5, get judgments instead of check results
            if layer_int in [4, 5] and not layer_results:
                # Filter judgments for this specific layer
                layer_judgments = [j for j in report.all_judgments
                                 if j.test_case and j.test_case.layer == layer_int]
            else:
                layer_judgments = []

            # Layer 2 starts collapsed (many tests); all others start open
            open_attr = "" if (layer_int == 2 and len(layer_results) > 10) else "open"

            pass_rate = summary['pass_rate']
            border_color = "#22c55e" if summary['failed'] == 0 else "#ef4444"

            # Render appropriate content based on layer
            if layer_int in [4, 5] and layer_judgments:
                layer_content = self._render_judgments_html(layer_judgments)
            else:
                layer_content = self._render_test_results_html(layer_results)

            html_parts.append(f"""
        <details class="layer" id="layer-{layer_int}" {open_attr} style="border-color: {border_color}">
            <summary>{layer_name}
                <span style="font-size:0.85em; font-weight:400; color:#666; margin-left:12px;">
                    {summary['passed']}/{summary['total']} passed &nbsp;({pass_rate:.1f}%)
                </span>
            </summary>
            <div class="layer-body">
                <div class="layer-stats">
                    <div class="stat">
                        <div class="stat-label">Total</div>
                        <div class="stat-value">{summary['total']}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Passed</div>
                        <div class="stat-value pass">{summary['passed']}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Failed</div>
                        <div class="stat-value fail">{summary['failed']}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Pass Rate</div>
                        <div class="stat-value">{pass_rate:.1f}%</div>
                    </div>
                </div>
                {layer_content}
            </div>
        </details>""")

        return ''.join(html_parts)

    def _render_test_results_html(self, results: List[CheckResult]) -> str:
        """Render test results in HTML."""
        if not results:
            return "<p>No tests in this layer</p>"

        html_parts = []
        for result in results:
            status_class = "passed" if result.passed else "failed"
            time_str = f"{result.execution_time_ms:.2f}ms" if result.execution_time_ms else "N/A"

            # Escape all user-controlled content to prevent XSS
            checkpoint_name = html.escape(result.checkpoint_name)
            message = html.escape(result.message)
            error_html = f'<div class="error">{html.escape(result.error)}</div>' if result.error else ''

            html_parts.append(f"""
            <div class="test-result {status_class}">
                <div class="test-name">
                    {'✓' if result.passed else '✗'} {checkpoint_name}
                </div>
                <div class="test-message">{message}</div>
                <div class="test-time">Execution time: {time_str}</div>
                {error_html}
            </div>""")

        return ''.join(html_parts)

    def _render_judgments_html(self, judgments: List[Judgment]) -> str:
        """Render Layer 4 LLM judgments in HTML."""
        if not judgments:
            return "<p>No tests in this layer</p>"

        html_parts = []
        for judgment in judgments:
            status_class = "passed" if judgment.passed else "failed"

            # Escape all user-controlled content to prevent XSS
            criterion = html.escape(judgment.criterion)
            rating = html.escape(judgment.rating)
            reasoning = html.escape(judgment.reasoning)

            html_parts.append(f"""
            <div class="test-result {status_class}">
                <div class="test-name">
                    {'✓' if judgment.passed else '✗'} {criterion}
                </div>
                <div class="test-message">
                    <strong>Rating:</strong> {rating}<br>
                    <strong>Reasoning:</strong> {reasoning}
                </div>
            </div>""")

        return ''.join(html_parts)

    def _render_failures_html(self, report: Report) -> str:
        """Render failure section in HTML."""
        html_output = """
        <div class="layer" id="failures" style="border-color: #ef4444;">
            <div class="layer-header" style="color: #ef4444;">Failures Summary</div>"""

        # Render CheckResult failures (Layers 0-3)
        for failure in report.failures:
            # Escape all user-controlled content to prevent XSS
            checkpoint_name = html.escape(failure.checkpoint_name)
            message = html.escape(failure.message)
            error_html = f'<div class="error">{html.escape(failure.error)}</div>' if failure.error else ''

            html_output += f"""
            <div class="test-result failed">
                <div class="test-name">Layer {failure.layer}: {checkpoint_name}</div>
                <div class="test-message">{message}</div>
                {error_html}
            </div>"""

        # Render Judgment failures (Layer 4)
        failed_judgments = [j for j in report.all_judgments if not j.passed]
        for judgment in failed_judgments:
            # Escape all user-controlled content to prevent XSS
            criterion = html.escape(judgment.criterion)
            rating = html.escape(judgment.rating)
            reasoning = html.escape(judgment.reasoning)

            html_output += f"""
            <div class="test-result failed">
                <div class="test-name">Layer 4: {criterion}</div>
                <div class="test-message">
                    <strong>Rating:</strong> {rating}<br>
                    <strong>Reasoning:</strong> {reasoning}
                </div>
            </div>"""

        html_output += "</div>"
        return html_output
