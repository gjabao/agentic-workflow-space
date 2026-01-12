#!/usr/bin/env python3
"""
Code Review Agent - DO Architecture Execution Script
Ruthlessly reviews Python scripts against directives for alignment, security, and efficiency.

This script acts as a wrapper to invoke the Reviewer Sub-Agent with clean, isolated context.
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, Tuple, Optional


class CodeReviewer:
    """
    Invokes the Reviewer Sub-Agent with context-isolated code snippets.

    Attributes:
        directive_path (str): Path to directive file
        script_path (str): Path to Python script to review
        context_limit (int): Maximum lines to include in review context
    """

    def __init__(self, directive_path: str, script_path: str, context_limit: int = 5000):
        self.directive_path = directive_path
        self.script_path = script_path
        self.context_limit = context_limit
        self.output_dir = '.tmp/reviews'
        os.makedirs(self.output_dir, exist_ok=True)

    def read_file(self, filepath: str, max_lines: Optional[int] = None) -> str:
        """
        Read file with optional line limit.

        Args:
            filepath: Path to file
            max_lines: Maximum lines to read (None = all)

        Returns:
            File content as string
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if max_lines and len(lines) > max_lines:
            lines = lines[:max_lines]
            lines.append(f"\n... (truncated at {max_lines} lines)")

        return ''.join(lines)

    def extract_critical_sections(self, code: str) -> Dict[str, str]:
        """
        Extract critical code sections for focused review.

        Args:
            code: Full Python code

        Returns:
            Dict mapping section name to code snippet
        """
        sections = {}
        lines = code.split('\n')

        # Security-critical patterns
        security_patterns = [
            'api_key', 'API_KEY', 'token', 'TOKEN', 'password', 'PASSWORD',
            'requests.', 'urllib.', 'subprocess.', 'os.system', 'eval('
        ]

        # Efficiency patterns
        efficiency_patterns = [
            'for ', 'while ', 'asyncio', 'concurrent', 'ThreadPoolExecutor',
            '.map(', '.gather(', 'time.sleep'
        ]

        security_lines = []
        efficiency_lines = []

        for i, line in enumerate(lines, 1):
            # Check security patterns
            if any(pattern in line for pattern in security_patterns):
                # Include 3 lines of context
                start = max(0, i - 3)
                end = min(len(lines), i + 3)
                security_lines.append((i, '\n'.join(lines[start:end])))

            # Check efficiency patterns
            if any(pattern in line for pattern in efficiency_patterns):
                start = max(0, i - 3)
                end = min(len(lines), i + 3)
                efficiency_lines.append((i, '\n'.join(lines[start:end])))

        if security_lines:
            sections['security_critical'] = '\n\n---\n\n'.join(
                [f"Line {num}:\n{snippet}" for num, snippet in security_lines[:10]]
            )

        if efficiency_lines:
            sections['efficiency_opportunities'] = '\n\n---\n\n'.join(
                [f"Line {num}:\n{snippet}" for num, snippet in efficiency_lines[:10]]
            )

        return sections

    def build_review_context(self) -> str:
        """
        Build isolated context for reviewer agent.

        Returns:
            Formatted context string for agent
        """
        directive_content = self.read_file(self.directive_path, max_lines=300)
        script_content = self.read_file(self.script_path, max_lines=self.context_limit)

        critical_sections = self.extract_critical_sections(script_content)

        context = f"""# CODE REVIEW REQUEST

## Directive: {os.path.basename(self.directive_path)}
```markdown
{directive_content}
```

---

## Script: {os.path.basename(self.script_path)}
```python
{script_content}
```

---

## Critical Sections Detected

"""

        for section_name, snippet in critical_sections.items():
            context += f"### {section_name.replace('_', ' ').title()}\n```python\n{snippet}\n```\n\n"

        context += """
---

## REVIEW CHECKLIST

Please provide a ruthlessly honest review covering:

1. **Directive Alignment** - Does code implement ALL directive requirements?
2. **Security Issues** - Any API key exposure, injection risks, OWASP violations?
3. **Efficiency Opportunities** - Can we get 10x gains (parallel, batch, cache)?
4. **Error Handling** - Proper timeouts, retries, graceful degradation?
5. **Code Quality** - Maintainability, single responsibility, DRY?

**Format your response as:**
```markdown
# Code Review: [Script Name]

## Executive Summary
- ✅ Alignment Score: X/10
- ⚡ Efficiency Score: X/10
- 🔒 Security Score: X/10
- 🛡️ Reliability Score: X/10

## Critical Issues
[List issues that MUST be fixed immediately]

## Efficiency Opportunities
[List 10x performance improvements]

## Recommendations
[Priority-ordered action items]
```

Be ruthlessly critical. Find the flaws. This is a production system.
"""

        return context

    def save_review_report(self, review_output: str) -> str:
        """
        Save review report to file.

        Args:
            review_output: Review report content

        Returns:
            Path to saved report
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        script_name = os.path.basename(self.script_path).replace('.py', '')
        filename = f"review_{script_name}_{timestamp}.md"
        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(review_output)

        return filepath

    def invoke_reviewer_agent(self) -> str:
        """
        Invoke the Reviewer Sub-Agent (simulated - in production would call Task tool).

        Returns:
            Review report output
        """
        context = self.build_review_context()

        print("=" * 70)
        print("🔍 REVIEWER AGENT INVOCATION")
        print("=" * 70)
        print(f"Directive: {self.directive_path}")
        print(f"Script: {self.script_path}")
        print(f"Context Size: {len(context)} characters")
        print("=" * 70)

        # In production, this would call the Task tool with subagent_type='general-purpose'
        # For now, we output the context to be reviewed by the orchestrator

        print("\n📋 REVIEW CONTEXT (to be passed to agent):\n")
        print(context)
        print("\n" + "=" * 70)
        print("⚠️  In production: This context would be sent to Task tool")
        print("⚠️  For now: Copy context above and manually review")
        print("=" * 70)

        return context

    def execute(self) -> Dict:
        """
        Execute the code review workflow.

        Returns:
            Dict with review results
        """
        print("🚀 Starting Code Review Agent...")

        try:
            # Build and invoke review
            review_context = self.invoke_reviewer_agent()

            # In production, would receive review_output from agent
            # For now, save the context
            context_file = self.save_review_report(review_context)

            print(f"\n✓ Review context saved: {context_file}")
            print("\n📌 NEXT STEP: Pass this context to your orchestrator agent for review")

            return {
                'success': True,
                'context_file': context_file,
                'context_size': len(review_context)
            }

        except Exception as e:
            print(f"❌ Review failed: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }


def main():
    """Main entry point for command-line usage."""
    parser = argparse.ArgumentParser(
        description='Review Python scripts against directives'
    )
    parser.add_argument(
        '--directive',
        required=True,
        help='Path to directive file (e.g., directives/scrape_leads.md)'
    )
    parser.add_argument(
        '--script',
        required=True,
        help='Path to Python script (e.g., execution/scrape_apify_leads.py)'
    )
    parser.add_argument(
        '--context_limit',
        type=int,
        default=5000,
        help='Maximum lines to review (default: 5000)'
    )

    args = parser.parse_args()

    reviewer = CodeReviewer(
        directive_path=args.directive,
        script_path=args.script,
        context_limit=args.context_limit
    )

    result = reviewer.execute()

    sys.exit(0 if result['success'] else 1)


if __name__ == '__main__':
    main()
