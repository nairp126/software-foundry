"""Demo script showing Git integration capabilities.

This example demonstrates the basic Git integration features of the
Autonomous Software Foundry, including:
- Repository initialization
- Conventional commits
- Feature branch management
- File change tracking
- Merge operations
- Semantic versioning tags
"""

import tempfile
import shutil
from pathlib import Path
from foundry.vcs.git_manager import GitManager, CommitType


def main():
    """Run Git integration demo."""
    # Create a temporary directory for the demo
    demo_dir = Path(tempfile.mkdtemp(prefix="foundry_git_demo_"))
    print(f"Demo repository: {demo_dir}\n")

    try:
        # Initialize Git manager
        git = GitManager(str(demo_dir))
        print("=" * 60)
        print("1. REPOSITORY INITIALIZATION")
        print("=" * 60)
        
        # Initialize repository
        success = git.initialize_repository()
        print(f"✓ Repository initialized: {success}")
        print(f"✓ Created .gitignore and .gitattributes")
        print(f"✓ Current branch: {git.get_current_branch()}")
        
        # Show initial commit
        commits = git.get_commit_history(limit=1)
        if commits:
            print(f"✓ Initial commit: {commits[0]['message']}\n")

        # Create some files and commit them
        print("=" * 60)
        print("2. CONVENTIONAL COMMITS")
        print("=" * 60)
        
        # Feature commit
        (demo_dir / "feature.py").write_text("def new_feature():\n    pass\n")
        git.create_commit(
            CommitType.FEAT,
            "add new feature module",
            scope="core"
        )
        print("✓ Created: feat(core): add new feature module")
        
        # Fix commit
        (demo_dir / "bugfix.py").write_text("def fix_bug():\n    pass\n")
        git.create_commit(
            CommitType.FIX,
            "resolve critical bug",
            scope="api"
        )
        print("✓ Created: fix(api): resolve critical bug")
        
        # Refactor commit with breaking change
        (demo_dir / "refactor.py").write_text("def refactored():\n    pass\n")
        git.create_commit(
            CommitType.REFACTOR,
            "restructure API endpoints",
            breaking=True
        )
        print("✓ Created: refactor!: restructure API endpoints\n")

        # Show commit history
        print("=" * 60)
        print("3. COMMIT HISTORY")
        print("=" * 60)
        commits = git.get_commit_history(limit=5)
        for i, commit in enumerate(commits, 1):
            print(f"{i}. {commit['message'][:50]}")
            print(f"   Author: {commit['author']}")
            print(f"   Hash: {commit['hash'][:8]}\n")

        # Feature branch management
        print("=" * 60)
        print("4. FEATURE BRANCH MANAGEMENT")
        print("=" * 60)
        
        # Create feature branch
        branch = git.create_feature_branch(
            "engineer",
            "user authentication"
        )
        print(f"✓ Created branch: {branch}")
        print(f"✓ Current branch: {git.get_current_branch()}")
        
        # Make changes on feature branch
        (demo_dir / "auth.py").write_text("def authenticate():\n    pass\n")
        git.create_commit(
            CommitType.FEAT,
            "implement user authentication",
            scope="auth"
        )
        print("✓ Committed changes on feature branch\n")

        # File change tracking
        print("=" * 60)
        print("5. FILE CHANGE TRACKING")
        print("=" * 60)
        
        # Create uncommitted changes
        (demo_dir / "new_file.py").write_text("# New file\n")
        (demo_dir / "auth.py").write_text("def authenticate():\n    return True\n")
        
        changed = git.get_changed_files()
        print(f"✓ Tracked {len(changed)} changed files:")
        for file in changed:
            print(f"  - {file}")
        print()

        # Merge operations
        print("=" * 60)
        print("6. MERGE OPERATIONS")
        print("=" * 60)
        
        # Commit the changes first
        git.create_commit(CommitType.FEAT, "update authentication")
        
        # Switch back to main and merge
        git.switch_branch("main")
        print(f"✓ Switched to: {git.get_current_branch()}")
        
        success, error = git.attempt_auto_merge(branch)
        if success:
            print(f"✓ Successfully merged {branch} into main")
        else:
            print(f"✗ Merge failed: {error}")
        print()

        # Semantic versioning tags
        print("=" * 60)
        print("7. SEMANTIC VERSIONING TAGS")
        print("=" * 60)
        
        # Create version tags
        git.create_tag("0.1.0", message="Initial alpha release")
        print("✓ Created tag: v0.1.0 (Initial alpha release)")
        
        git.create_tag("0.2.0-beta", message="Beta release with new features")
        print("✓ Created tag: v0.2.0-beta (Beta release)")
        
        git.create_tag("1.0.0", message="First stable release")
        print("✓ Created tag: v1.0.0 (First stable release)")
        
        latest = git.get_latest_tag()
        print(f"✓ Latest tag: {latest}\n")

        # Summary
        print("=" * 60)
        print("DEMO COMPLETE")
        print("=" * 60)
        print("✓ All Git integration features demonstrated successfully")
        print(f"✓ Repository location: {demo_dir}")
        print("\nFeatures demonstrated:")
        print("  1. Repository initialization with .gitignore and .gitattributes")
        print("  2. Conventional commit messages (feat, fix, refactor)")
        print("  3. Feature branch creation with naming convention")
        print("  4. File change tracking")
        print("  5. Automatic merge operations")
        print("  6. Semantic versioning tags")

    finally:
        # Cleanup
        print(f"\nCleaning up demo repository...")
        try:
            shutil.rmtree(demo_dir)
            print("✓ Cleanup complete")
        except Exception as e:
            print(f"Note: Manual cleanup may be needed: {demo_dir}")
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
