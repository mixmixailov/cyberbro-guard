#!/usr/bin/env python3
"""
Script to generate bug reproduction tests from GitHub issue ID.

Usage:
    python scripts/create_repro_test.py --issue 123 --area handlers --slug "callback-processing-error"
    python scripts/create_repro_test.py --issue 456 --area services --slug "payment-calculation-bug" --e2e
"""

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


AREA_MAPPINGS = {
    "handlers": "Telegram message/callback handlers",
    "services": "Business logic services", 
    "db": "Database layer",
    "payments": "Payment system",
    "queue": "Queue/DLQ system", 
    "i18n": "Internationalization",
    "ci": "CI/CD pipeline"
}

UNIT_TEST_TEMPLATE = '''"""
Bug reproduction test for issue #{issue_id}.

GitHub Issue: https://github.com/mixmixailov/cyberbro-guard/issues/{issue_id}
Area: {area_description}
Created: {timestamp}
"""

import pytest

# TODO: Add specific imports for the bug being reproduced
# from app.{area}.{module} import {function_or_class}


@pytest.mark.bug
@pytest.mark.issue_id("{issue_id}")
@pytest.mark.{area}
def test_{slug}_repro():
    """
    Reproduces bug reported in issue #{issue_id}.
    
    TODO: Update this description with:
    - Brief description of the bug
    - Steps to reproduce the issue
    - Expected vs actual behavior
    
    This test should FAIL until the bug is fixed.
    """
    # TODO: Arrange - Set up test conditions that trigger the bug
    # Example: mock objects, test data, configuration
    
    # TODO: Act - Execute the minimal code path that reproduces the issue
    # Example: call the function/method that contains the bug
    
    # TODO: Assert - Verify the bug occurs (test should fail until bug is fixed)
    # Use pytest.fail() with descriptive message if the bug is hard to assert
    pytest.fail("TODO: Implement bug reproduction for issue #{issue_id}")


# TODO: Add helper functions specific to this bug reproduction
def setup_bug_conditions():
    """Helper to set up conditions that trigger the bug."""
    pass


def verify_bug_behavior():
    """Helper to verify the bug occurs as expected.""" 
    pass
'''

E2E_TEST_TEMPLATE = '''/**
 * E2E bug reproduction test for issue #{issue_id}.
 * 
 * GitHub Issue: https://github.com/mixmixailov/cyberbro-guard/issues/{issue_id}
 * Area: {area_description}
 * Created: {timestamp}
 */

import {{ test, expect }} from '@playwright/test';

test.describe('Bug Reproduction - Issue #{issue_id}', () => {{
  test('reproduces {slug} bug #{issue_id} @bug @issue_id:{issue_id}', async ({{ page }}) => {{
    /**
     * TODO: Update this description with:
     * - Brief description of the user-facing bug
     * - User workflow steps that trigger the issue
     * - Expected vs actual user experience
     * 
     * This test should FAIL until the bug is fixed.
     */

    // TODO: Arrange - Setup initial conditions for user workflow
    // Example: navigate to specific page, login user, setup data
    
    // TODO: Act - Reproduce the user workflow that triggers the bug
    // Example: click buttons, fill forms, navigate pages
    
    // TODO: Assert - Verify the bug occurs from user perspective
    // Example: check for error messages, missing data, broken UI
    
    // Placeholder assertion - replace with actual bug verification
    throw new Error('TODO: Implement E2E bug reproduction for issue #{issue_id}');
  }});
}});

// TODO: Add helper functions for this E2E bug reproduction
async function setupUserWorkflow(page: any) {{
  // Helper to setup user workflow conditions
}}

async function verifyBugFromUserPerspective(page: any) {{
  // Helper to verify bug from user's perspective
}}
'''


def create_unit_test(issue_id: str, area: str, slug: str) -> str:
    """Generate unit test file content."""
    return UNIT_TEST_TEMPLATE.format(
        issue_id=issue_id,
        area=area,
        area_description=AREA_MAPPINGS.get(area, area),
        slug=slug.replace('-', '_'),
        timestamp=datetime.now().isoformat()
    )


def create_e2e_test(issue_id: str, area: str, slug: str) -> str:
    """Generate E2E test file content.""" 
    return E2E_TEST_TEMPLATE.format(
        issue_id=issue_id,
        area_description=AREA_MAPPINGS.get(area, area),
        slug=slug,
        timestamp=datetime.now().isoformat()
    )


def write_test_file(content: str, file_path: Path) -> None:
    """Write test content to file, creating directories if needed."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Created: {file_path}")


def main():
    parser = argparse.ArgumentParser(description='Generate bug reproduction tests')
    parser.add_argument('--issue', required=True, help='GitHub issue ID (e.g., 123)')
    parser.add_argument(
        '--area', 
        required=True, 
        choices=list(AREA_MAPPINGS.keys()),
        help='Application area for the bug'
    )
    parser.add_argument(
        '--slug', 
        required=True,
        help='Descriptive slug for the bug (e.g., "callback-processing-error")'
    )
    parser.add_argument(
        '--e2e', 
        action='store_true',
        help='Also create E2E test for user-facing bugs'
    )
    parser.add_argument(
        '--base-dir',
        default='.',
        help='Base project directory (default: current directory)'
    )
    
    args = parser.parse_args()
    
    base_path = Path(args.base_dir)
    issue_id = args.issue
    area = args.area
    slug = args.slug
    
    # Validate inputs
    if not slug.replace('-', '').replace('_', '').isalnum():
        print("❌ Error: Slug should only contain letters, numbers, hyphens, and underscores")
        sys.exit(1)
    
    # Create unit test
    unit_test_content = create_unit_test(issue_id, area, slug)
    unit_test_path = base_path / f"tests/unit/{area}/test_{slug.replace('-', '_')}_repro.py"
    write_test_file(unit_test_content, unit_test_path)
    
    # Create E2E test if requested
    if args.e2e:
        e2e_test_content = create_e2e_test(issue_id, area, slug)
        e2e_test_path = base_path / f"tests/e2e/{slug}.spec.ts"
        write_test_file(e2e_test_content, e2e_test_path)
    
    print(f"\\n🎯 Bug reproduction tests created for issue #{issue_id}")
    print(f"📋 Area: {area} ({AREA_MAPPINGS.get(area, area)})")
    print(f"🏷️  Slug: {slug}")
    
    print("\\n📝 Next steps:")
    print(f"1. Update the generated test(s) with actual bug reproduction logic")
    print(f"2. Ensure tests FAIL until the bug is fixed")
    print(f"3. Run tests: pytest -m 'bug and issue_id:{issue_id}'")
    if args.e2e:
        print(f"4. Run E2E test: npm test -- tests/e2e/{slug}.spec.ts")


if __name__ == '__main__':
    main()
