#!/usr/bin/env python3
"""Local PR Gate validation script.

Run this script locally to check if your changes would pass PR Gate
before creating a pull request.

Usage:
    python scripts/check_pr_gate_local.py
    python scripts/check_pr_gate_local.py --target main
    python scripts/check_pr_gate_local.py --target origin/main
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_git_command(cmd: list[str]) -> str:
    """Run git command and return output."""
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            check=True,
            cwd=Path(__file__).parent.parent
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Git command failed: {' '.join(cmd)}")
        print(f"Error: {e.stderr}")
        sys.exit(1)


def get_changed_files(target_branch: str) -> list[str]:
    """Get list of changed files compared to target branch."""
    cmd = ["git", "diff", "--name-only", f"{target_branch}..HEAD"]
    output = run_git_command(cmd)
    return [line.strip() for line in output.split('\n') if line.strip()]


def count_code_lines(files: list[str], target_branch: str) -> int:
    """Count changed lines in code files (excluding docs/ and tests/)."""
    total_lines = 0
    
    for file in files:
        # Skip docs/ and tests/ directories
        if file.startswith(('docs/', 'tests/')):
            print(f"⏭️  Skipping documentation/test file: {file}")
            continue
        
        # Skip deleted files
        if not Path(file).exists():
            print(f"🗑️  File deleted: {file}")
            continue
        
        # Count lines changed in this file
        cmd = ["git", "diff", "--numstat", f"{target_branch}..HEAD", "--", file]
        try:
            output = run_git_command(cmd)
            if output:
                parts = output.split('\t')
                if len(parts) >= 2:
                    additions = int(parts[0]) if parts[0].isdigit() else 0
                    deletions = int(parts[1]) if parts[1].isdigit() else 0
                    file_lines = additions + deletions
                    total_lines += file_lines
                    print(f"📝 {file}: {file_lines} lines ({additions}+{deletions})")
        except (ValueError, subprocess.CalledProcessError):
            print(f"⚠️  Could not count lines for: {file}")
    
    return total_lines


def check_app_and_test_changes(files: list[str]) -> tuple[int, int]:
    """Check for app/ and test file changes."""
    app_changes = sum(1 for f in files if f.startswith('app/'))
    test_changes = sum(1 for f in files if f.startswith('tests/'))
    return app_changes, test_changes


def check_critical_and_doc_changes(files: list[str]) -> tuple[int, int]:
    """Check for critical system and documentation changes."""
    critical_changes = sum(1 for f in files if 'payments' in f or 'queue' in f)
    doc_changes = sum(1 for f in files if f in ['docs/spec.md', 'docs/scope.md'])
    return critical_changes, doc_changes


def main():
    parser = argparse.ArgumentParser(description="Local PR Gate validation")
    parser.add_argument(
        "--target", 
        default="main", 
        help="Target branch to compare against (default: main)"
    )
    args = parser.parse_args()
    
    print(f"🔍 PR Gate Local Validation")
    print(f"Target branch: {args.target}")
    print("=" * 50)
    
    # Get changed files
    try:
        changed_files = get_changed_files(args.target)
    except SystemExit:
        print("❌ Could not get changed files. Make sure you're in a git repository.")
        print("💡 Try: git fetch origin && python scripts/check_pr_gate_local.py --target origin/main")
        sys.exit(1)
    
    if not changed_files:
        print("✅ No changes detected.")
        return
    
    print(f"📋 Changed files ({len(changed_files)}):")
    for file in changed_files:
        print(f"  - {file}")
    print()
    
    # Check PR size
    code_lines = count_code_lines(changed_files, args.target)
    print(f"📏 Code lines changed: {code_lines}/400")
    
    size_status = "✅" if code_lines <= 400 else "❌"
    print(f"{size_status} PR Size Check: {'PASS' if code_lines <= 400 else 'FAIL'}")
    
    if code_lines > 400:
        print("💡 Consider splitting this PR into smaller changes:")
        print("   - Extract refactoring to separate PR")
        print("   - Move documentation updates to separate PR")
        print("   - Split unrelated features into different PRs")
    elif code_lines > 300:
        print("⚠️  Large PR warning: Consider splitting for easier review")
    print()
    
    # Check test requirements
    app_changes, test_changes = check_app_and_test_changes(changed_files)
    print(f"🧪 App changes: {app_changes}, Test changes: {test_changes}")
    
    test_required = app_changes > 0
    test_present = test_changes > 0
    test_status = "✅" if not test_required or test_present else "❌"
    
    print(f"{test_status} Test Requirement: {'PASS' if not test_required or test_present else 'FAIL'}")
    
    if test_required and not test_present:
        print("💡 Add tests for your app/ changes:")
        print("   - tests/unit/ for new functions/methods")
        print("   - tests/regression/ for bug fixes")
        print("   - tests/ for integration tests")
    elif test_required and test_present:
        print("✅ Good: Code changes include test updates")
    print()
    
    # Check documentation requirements
    critical_changes, doc_changes = check_critical_and_doc_changes(changed_files)
    print(f"📚 Critical changes: {critical_changes}, Doc changes: {doc_changes}")
    
    doc_required = critical_changes > 0
    doc_present = doc_changes > 0
    doc_status = "✅" if not doc_required or doc_present else "❌"
    
    print(f"{doc_status} Documentation Requirement: {'PASS' if not doc_required or doc_present else 'FAIL'}")
    
    if doc_required and not doc_present:
        print("💡 Update documentation for critical changes:")
        print("   - docs/spec.md for technical specifications")
        print("   - docs/scope.md for feature scope and requirements")
    elif doc_required and doc_present:
        print("✅ Good: Critical changes include documentation updates")
    print()
    
    # Overall result
    all_checks_pass = (
        code_lines <= 400 and
        (not test_required or test_present) and
        (not doc_required or doc_present)
    )
    
    if all_checks_pass:
        print("🎉 All PR Gate checks would PASS!")
        print("✅ Your PR is ready for submission.")
    else:
        print("❌ Some PR Gate checks would FAIL!")
        print("🔧 Please address the issues above before creating your PR.")
        sys.exit(1)


if __name__ == "__main__":
    main()
