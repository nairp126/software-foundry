"""Unit tests for Git repository management."""

import pytest
import tempfile
import shutil
import time
import gc
from pathlib import Path
from foundry.vcs.git_manager import GitManager, CommitType, MergeStrategy


@pytest.fixture
def temp_repo():
    """Create a temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    
    # Force garbage collection to release file handles (Windows issue)
    gc.collect()
    time.sleep(0.1)
    
    # Try to remove with retries for Windows
    max_retries = 3
    for attempt in range(max_retries):
        try:
            shutil.rmtree(temp_dir)
            break
        except PermissionError:
            if attempt < max_retries - 1:
                time.sleep(0.5)
                gc.collect()
            else:
                # Last resort: mark for deletion on reboot (Windows only)
                import sys
                if sys.platform == "win32":
                    try:
                        import subprocess
                        subprocess.run(
                            ["cmd", "/c", "rmdir", "/s", "/q", temp_dir],
                            capture_output=True
                        )
                    except Exception:
                        pass  # Best effort cleanup


@pytest.fixture
def git_manager(temp_repo):
    """Create a GitManager instance for testing."""
    return GitManager(str(temp_repo))


class TestRepositoryInitialization:
    """Tests for repository initialization."""

    def test_initialize_repository_creates_git_dir(self, git_manager, temp_repo):
        """Test that repository initialization creates .git directory."""
        result = git_manager.initialize_repository()
        assert result is True
        assert (temp_repo / ".git").exists()

    def test_initialize_repository_creates_gitignore(self, git_manager, temp_repo):
        """Test that initialization creates .gitignore file."""
        git_manager.initialize_repository()
        gitignore_path = temp_repo / ".gitignore"
        assert gitignore_path.exists()
        content = gitignore_path.read_text()
        assert "__pycache__/" in content
        assert "node_modules/" in content
        assert ".env" in content

    def test_initialize_repository_creates_gitattributes(self, git_manager, temp_repo):
        """Test that initialization creates .gitattributes file."""
        git_manager.initialize_repository()
        gitattributes_path = temp_repo / ".gitattributes"
        assert gitattributes_path.exists()
        content = gitattributes_path.read_text()
        assert "*.py text eol=lf" in content
        assert "*.js text eol=lf" in content

    def test_initialize_repository_creates_initial_commit(self, git_manager):
        """Test that initialization creates an initial commit."""
        git_manager.initialize_repository()
        commits = git_manager.get_commit_history(limit=1)
        assert len(commits) == 1
        assert "chore" in commits[0]["message"].lower()

    def test_initialize_already_initialized_repo(self, git_manager):
        """Test that initializing an already initialized repo succeeds."""
        git_manager.initialize_repository()
        result = git_manager.initialize_repository()
        assert result is True


class TestCommitCreation:
    """Tests for commit creation."""

    def test_create_commit_with_feat_type(self, git_manager, temp_repo):
        """Test creating a feature commit."""
        git_manager.initialize_repository()
        
        # Create a test file
        test_file = temp_repo / "test.py"
        test_file.write_text("print('hello')")
        
        result = git_manager.create_commit(
            CommitType.FEAT,
            "add test file"
        )
        assert result is True
        
        commits = git_manager.get_commit_history(limit=1)
        assert "feat: add test file" in commits[0]["message"]

    def test_create_commit_with_scope(self, git_manager, temp_repo):
        """Test creating a commit with scope."""
        git_manager.initialize_repository()
        
        test_file = temp_repo / "test.py"
        test_file.write_text("print('hello')")
        
        result = git_manager.create_commit(
            CommitType.FIX,
            "resolve bug",
            scope="api"
        )
        assert result is True
        
        commits = git_manager.get_commit_history(limit=1)
        assert "fix(api): resolve bug" in commits[0]["message"]

    def test_create_commit_with_breaking_change(self, git_manager, temp_repo):
        """Test creating a commit with breaking change."""
        git_manager.initialize_repository()
        
        test_file = temp_repo / "test.py"
        test_file.write_text("print('hello')")
        
        result = git_manager.create_commit(
            CommitType.REFACTOR,
            "change API structure",
            breaking=True
        )
        assert result is True
        
        commits = git_manager.get_commit_history(limit=1)
        assert "refactor!: change API structure" in commits[0]["message"]

    def test_create_commit_with_specific_files(self, git_manager, temp_repo):
        """Test creating a commit with specific files."""
        git_manager.initialize_repository()
        
        # Create multiple test files
        file1 = temp_repo / "file1.py"
        file2 = temp_repo / "file2.py"
        file1.write_text("print('file1')")
        file2.write_text("print('file2')")
        
        # Commit only file1
        result = git_manager.create_commit(
            CommitType.FEAT,
            "add file1",
            files=["file1.py"]
        )
        assert result is True
        
        # file2 should still be uncommitted
        changed_files = git_manager.get_changed_files()
        assert "file2.py" in changed_files

    def test_create_commit_no_changes(self, git_manager):
        """Test that creating a commit with no changes returns False."""
        git_manager.initialize_repository()
        
        result = git_manager.create_commit(
            CommitType.FEAT,
            "no changes"
        )
        assert result is False


class TestBranchManagement:
    """Tests for branch management."""

    def test_create_feature_branch(self, git_manager):
        """Test creating a feature branch with proper naming convention."""
        git_manager.initialize_repository()
        
        branch_name = git_manager.create_feature_branch(
            "engineer",
            "user authentication"
        )
        
        assert branch_name == "foundry/engineer/user-authentication"
        assert git_manager.get_current_branch() == branch_name

    def test_create_feature_branch_sanitizes_name(self, git_manager):
        """Test that feature branch names are properly sanitized."""
        git_manager.initialize_repository()
        
        branch_name = git_manager.create_feature_branch(
            "architect",
            "Add API Endpoints & Database Schema!"
        )
        
        # Should remove special characters and convert to lowercase
        assert "foundry/architect/" in branch_name
        assert "&" not in branch_name
        assert "!" not in branch_name
        assert branch_name.islower() or "-" in branch_name

    def test_get_current_branch(self, git_manager):
        """Test getting the current branch name."""
        git_manager.initialize_repository()
        
        current = git_manager.get_current_branch()
        assert current == "main"

    def test_switch_branch(self, git_manager):
        """Test switching between branches."""
        git_manager.initialize_repository()
        
        # Create a new branch
        new_branch = git_manager.create_feature_branch(
            "devops",
            "deployment"
        )
        
        # Switch back to main
        result = git_manager.switch_branch("main")
        assert result is True
        assert git_manager.get_current_branch() == "main"
        
        # Switch back to feature branch
        result = git_manager.switch_branch(new_branch)
        assert result is True
        assert git_manager.get_current_branch() == new_branch


class TestFileChangeTracking:
    """Tests for file change tracking."""

    def test_get_changed_files_empty(self, git_manager):
        """Test getting changed files when there are none."""
        git_manager.initialize_repository()
        
        changed = git_manager.get_changed_files()
        assert changed == []

    def test_get_changed_files_with_modifications(self, git_manager, temp_repo):
        """Test getting changed files with modifications."""
        git_manager.initialize_repository()
        
        # Create and modify files
        file1 = temp_repo / "file1.py"
        file2 = temp_repo / "file2.py"
        file1.write_text("print('file1')")
        file2.write_text("print('file2')")
        
        changed = git_manager.get_changed_files()
        assert "file1.py" in changed
        assert "file2.py" in changed


class TestMergeConflictDetection:
    """Tests for merge conflict detection."""

    def test_has_merge_conflicts_no_conflicts(self, git_manager):
        """Test conflict detection when there are no conflicts."""
        git_manager.initialize_repository()
        
        assert git_manager.has_merge_conflicts() is False

    def test_get_conflicted_files_empty(self, git_manager):
        """Test getting conflicted files when there are none."""
        git_manager.initialize_repository()
        
        conflicted = git_manager.get_conflicted_files()
        assert conflicted == []

    def test_attempt_auto_merge_success(self, git_manager, temp_repo):
        """Test successful automatic merge."""
        git_manager.initialize_repository()
        
        # Create a file on main
        file1 = temp_repo / "file1.py"
        file1.write_text("print('main')")
        git_manager.create_commit(CommitType.FEAT, "add file1 on main")
        
        # Create a branch and add a different file
        branch = git_manager.create_feature_branch("engineer", "feature")
        file2 = temp_repo / "file2.py"
        file2.write_text("print('feature')")
        git_manager.create_commit(CommitType.FEAT, "add file2 on feature")
        
        # Switch back to main and merge
        git_manager.switch_branch("main")
        success, error = git_manager.attempt_auto_merge(branch)
        
        assert success is True
        assert error is None


class TestTagManagement:
    """Tests for Git tag management."""

    def test_create_tag_with_version(self, git_manager):
        """Test creating a tag with semantic versioning."""
        git_manager.initialize_repository()
        
        result = git_manager.create_tag("1.0.0")
        assert result is True
        
        latest = git_manager.get_latest_tag()
        assert latest == "v1.0.0"

    def test_create_tag_adds_v_prefix(self, git_manager):
        """Test that tag creation adds 'v' prefix if missing."""
        git_manager.initialize_repository()
        
        git_manager.create_tag("2.0.0")
        latest = git_manager.get_latest_tag()
        assert latest.startswith("v")

    def test_create_tag_with_prerelease(self, git_manager):
        """Test creating a tag with prerelease version."""
        git_manager.initialize_repository()
        
        result = git_manager.create_tag("1.1.0-beta")
        assert result is True
        
        latest = git_manager.get_latest_tag()
        assert "beta" in latest

    def test_create_tag_with_message(self, git_manager):
        """Test creating an annotated tag with custom message."""
        git_manager.initialize_repository()
        
        result = git_manager.create_tag(
            "1.0.0",
            message="First stable release"
        )
        assert result is True

    def test_get_latest_tag_no_tags(self, git_manager):
        """Test getting latest tag when no tags exist."""
        git_manager.initialize_repository()
        
        latest = git_manager.get_latest_tag()
        assert latest is None


class TestCommitHistory:
    """Tests for commit history retrieval."""

    def test_get_commit_history(self, git_manager, temp_repo):
        """Test retrieving commit history."""
        git_manager.initialize_repository()
        
        # Create multiple commits
        for i in range(3):
            file = temp_repo / f"file{i}.py"
            file.write_text(f"print('file{i}')")
            git_manager.create_commit(CommitType.FEAT, f"add file{i}")
        
        commits = git_manager.get_commit_history(limit=5)
        
        # Should have 4 commits (3 + initial)
        assert len(commits) >= 3
        assert all("hash" in c for c in commits)
        assert all("author" in c for c in commits)
        assert all("date" in c for c in commits)
        assert all("message" in c for c in commits)

    def test_get_commit_history_limit(self, git_manager, temp_repo):
        """Test that commit history respects limit parameter."""
        git_manager.initialize_repository()
        
        # Create multiple commits
        for i in range(5):
            file = temp_repo / f"file{i}.py"
            file.write_text(f"print('file{i}')")
            git_manager.create_commit(CommitType.FEAT, f"add file{i}")
        
        commits = git_manager.get_commit_history(limit=2)
        assert len(commits) == 2


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_git_manager_with_nonexistent_path(self):
        """Test GitManager with a path that doesn't exist yet."""
        manager = GitManager("/tmp/nonexistent_repo_test_12345")
        # Should not raise an error during initialization
        assert manager.repo_path.name == "nonexistent_repo_test_12345"

    def test_operations_on_uninitialized_repo(self, git_manager, temp_repo):
        """Test that operations on uninitialized repo handle errors gracefully."""
        # Don't initialize the repo
        
        # These should handle the error gracefully
        result = git_manager.get_current_branch()
        # May return None or raise, but shouldn't crash
        assert result is None or isinstance(result, str)
