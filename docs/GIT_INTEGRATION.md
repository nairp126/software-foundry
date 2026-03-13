# Git Integration

The Autonomous Software Foundry includes comprehensive Git integration for version control of generated projects. This document describes the Git management capabilities and how to use them.

## Overview

The Git integration provides:

- **Repository Initialization**: Automatic setup with `.gitignore` and `.gitattributes`
- **Conventional Commits**: Standardized commit messages following conventional commit format
- **Feature Branches**: Automated branch creation with naming conventions
- **File Change Tracking**: Monitor uncommitted changes
- **Merge Conflict Detection**: Identify and handle merge conflicts
- **Semantic Versioning**: Tag releases with semantic version numbers

## Architecture

The Git integration is implemented in the `foundry.vcs` module:

```
src/foundry/vcs/
├── __init__.py
└── git_manager.py    # Core Git operations
```

## GitManager Class

The `GitManager` class provides all Git operations for a repository.

### Initialization

```python
from foundry.vcs import GitManager

# Create a Git manager for a repository
git = GitManager("/path/to/repository")
```

### Repository Initialization

Initialize a new Git repository with proper configuration:

```python
# Initialize with default settings
git.initialize_repository()

# Customize initialization
git.initialize_repository(
    initial_branch="main",
    create_gitignore=True,
    create_gitattributes=True
)
```

**What it does:**
- Creates `.git` directory
- Generates comprehensive `.gitignore` for Python, Node.js, and common IDEs
- Creates `.gitattributes` for consistent line endings
- Configures Git user (Software Foundry)
- Creates initial commit

**Implements:** Requirement 18.1

### Conventional Commits

Create commits following the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```python
from foundry.vcs.git_manager import CommitType

# Simple feature commit
git.create_commit(
    CommitType.FEAT,
    "add user authentication"
)

# Commit with scope
git.create_commit(
    CommitType.FIX,
    "resolve login bug",
    scope="auth"
)

# Breaking change
git.create_commit(
    CommitType.REFACTOR,
    "restructure API",
    breaking=True
)

# Commit with detailed body
git.create_commit(
    CommitType.FEAT,
    "implement caching",
    scope="performance",
    body="Added Redis caching layer for API responses.\nReduces response time by 60%."
)

# Commit specific files only
git.create_commit(
    CommitType.DOCS,
    "update README",
    files=["README.md", "docs/setup.md"]
)
```

**Commit Types:**
- `FEAT`: New feature
- `FIX`: Bug fix
- `REFACTOR`: Code refactoring
- `DOCS`: Documentation changes
- `TEST`: Test additions or modifications
- `CHORE`: Maintenance tasks
- `STYLE`: Code style changes
- `PERF`: Performance improvements

**Commit Message Format:**
```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Implements:** Requirement 18.2

### Feature Branch Management

Create feature branches following the foundry naming convention:

```python
# Create a feature branch
branch_name = git.create_feature_branch(
    agent_name="engineer",
    feature_description="user authentication",
    base_branch="main"
)
# Creates: foundry/engineer/user-authentication

# Get current branch
current = git.get_current_branch()

# Switch branches
git.switch_branch("main")
git.switch_branch(branch_name)
```

**Branch Naming Convention:**
```
foundry/<agent-name>/<feature-description>
```

Examples:
- `foundry/engineer/user-authentication`
- `foundry/architect/database-schema`
- `foundry/devops/deployment-pipeline`

**Implements:** Requirement 18.3

### File Change Tracking

Track uncommitted changes in the repository:

```python
# Get list of changed files
changed_files = git.get_changed_files()

for file in changed_files:
    print(f"Modified: {file}")

# Check if there are any changes
has_changes = len(changed_files) > 0
```

**Implements:** Requirement 18.4

### Merge Conflict Detection and Resolution

Detect and attempt to resolve merge conflicts:

```python
from foundry.vcs.git_manager import MergeStrategy

# Check for conflicts
if git.has_merge_conflicts():
    conflicted = git.get_conflicted_files()
    print(f"Conflicts in: {conflicted}")

# Attempt automatic merge
success, error = git.attempt_auto_merge(
    branch_name="foundry/engineer/feature",
    strategy=MergeStrategy.RECURSIVE
)

if success:
    print("Merge successful")
else:
    print(f"Merge failed: {error}")
    # Escalate to human review
    git.abort_merge()
```

**Merge Strategies:**
- `RECURSIVE`: Three-way merge (default)
- `OURS`: Prefer current branch changes
- `THEIRS`: Prefer incoming branch changes

**Implements:** Requirement 18.5

### Semantic Versioning Tags

Create Git tags for releases:

```python
# Create a version tag
git.create_tag("1.0.0", message="First stable release")

# Create a prerelease tag
git.create_tag("1.1.0-beta", message="Beta release")

# Get the latest tag
latest = git.get_latest_tag()
print(f"Latest version: {latest}")
```

**Version Format:**
- `v1.0.0` - Major release
- `v1.1.0` - Minor release
- `v1.1.1` - Patch release
- `v2.0.0-alpha` - Prerelease
- `v2.0.0-beta.1` - Numbered prerelease

**Implements:** Requirement 18.8

### Commit History

Retrieve commit history:

```python
# Get recent commits
commits = git.get_commit_history(limit=10)

for commit in commits:
    print(f"{commit['hash'][:8]} - {commit['message']}")
    print(f"  Author: {commit['author']}")
    print(f"  Date: {commit['date']}")
```

## Integration with Agents

The Git integration is designed to work seamlessly with the foundry's agent system:

### Engineering Agent

```python
from foundry.vcs import GitManager
from foundry.vcs.git_manager import CommitType

class EngineeringAgent:
    def implement_feature(self, project_path, feature_spec):
        git = GitManager(project_path)
        
        # Create feature branch
        branch = git.create_feature_branch(
            "engineer",
            feature_spec.name
        )
        
        # Generate code
        code = self.generate_code(feature_spec)
        
        # Commit changes
        git.create_commit(
            CommitType.FEAT,
            f"implement {feature_spec.name}",
            scope=feature_spec.module
        )
        
        return branch
```

### DevOps Agent

```python
class DevOpsAgent:
    def deploy_release(self, project_path, version):
        git = GitManager(project_path)
        
        # Create release tag
        git.create_tag(
            version,
            message=f"Release {version}"
        )
        
        # Deploy to production
        self.deploy_to_cloud(project_path, version)
```

## File Locking for Conflict Prevention

The foundry implements file-locking mechanisms to prevent merge conflicts when multiple agents work on the same project:

```python
from foundry.vcs import GitManager

class AgentCoordinator:
    def __init__(self, project_path):
        self.git = GitManager(project_path)
        self.file_locks = {}
    
    def acquire_file_lock(self, agent_id, file_path):
        """Acquire exclusive lock on a file."""
        if file_path in self.file_locks:
            return False
        self.file_locks[file_path] = agent_id
        return True
    
    def release_file_lock(self, agent_id, file_path):
        """Release file lock."""
        if self.file_locks.get(file_path) == agent_id:
            del self.file_locks[file_path]
            return True
        return False
```

**Implements:** Requirement 18.4

## Error Handling

The Git integration includes comprehensive error handling:

```python
try:
    git.create_commit(CommitType.FEAT, "new feature")
except subprocess.CalledProcessError as e:
    logger.error(f"Git command failed: {e.stderr}")
    # Handle error appropriately
```

All Git operations return boolean success indicators or raise exceptions that can be caught and handled by the calling code.

## Testing

The Git integration includes comprehensive unit tests:

```bash
# Run Git integration tests
pytest tests/test_git_manager.py -v

# Run with coverage
pytest tests/test_git_manager.py --cov=foundry.vcs
```

## Example Usage

See `examples/git_integration_demo.py` for a complete demonstration of all Git integration features.

```bash
# Run the demo
python examples/git_integration_demo.py
```

## Configuration

Git configuration is managed per-repository:

```python
git = GitManager(project_path)

# Default configuration
# User: Software Foundry
# Email: foundry@autonomous.local
# Initial branch: main
```

## Best Practices

1. **Always initialize repositories**: Call `initialize_repository()` before any other Git operations
2. **Use conventional commits**: Follow the commit type conventions for consistency
3. **Create feature branches**: Use feature branches for all agent work
4. **Check for conflicts**: Always check for conflicts before merging
5. **Tag releases**: Create tags for all production deployments
6. **Atomic commits**: Commit related changes together

## Limitations

- **Windows file locking**: Git objects may remain locked on Windows, requiring delayed cleanup
- **No remote operations**: Current implementation focuses on local repository operations
- **No GPG signing**: Signed commits (Requirement 18.9) not yet implemented

## Future Enhancements

Planned improvements include:

- Remote repository integration (GitHub, GitLab, Bitbucket)
- Pull request automation
- GPG commit signing
- Advanced conflict resolution strategies
- Git hooks for automated quality checks

## Requirements Coverage

This implementation satisfies the following requirements:

- ✅ **18.1**: Repository initialization with .gitignore and .gitattributes
- ✅ **18.2**: Conventional commit messages
- ✅ **18.3**: Feature branch naming convention
- ✅ **18.4**: File change tracking and locking mechanisms
- ✅ **18.5**: Merge conflict detection and automatic resolution
- ✅ **18.8**: Semantic versioning tags
- ⏳ **18.6**: Remote repository integration (future)
- ⏳ **18.7**: Pull request automation (future)
- ⏳ **18.9**: GPG signed commits (future)

## API Reference

### GitManager

#### `__init__(repo_path: str)`
Initialize Git manager for a repository.

#### `initialize_repository(initial_branch: str = "main", create_gitignore: bool = True, create_gitattributes: bool = True) -> bool`
Initialize a Git repository with configuration files.

#### `create_commit(commit_type: CommitType, description: str, scope: Optional[str] = None, body: Optional[str] = None, breaking: bool = False, files: Optional[List[str]] = None) -> bool`
Create a conventional commit.

#### `create_feature_branch(agent_name: str, feature_description: str, base_branch: str = "main") -> Optional[str]`
Create a feature branch following naming convention.

#### `get_current_branch() -> Optional[str]`
Get the name of the current branch.

#### `switch_branch(branch_name: str) -> bool`
Switch to a different branch.

#### `get_changed_files() -> List[str]`
Get list of files with uncommitted changes.

#### `has_merge_conflicts() -> bool`
Check if there are merge conflicts.

#### `get_conflicted_files() -> List[str]`
Get list of files with merge conflicts.

#### `attempt_auto_merge(branch_name: str, strategy: MergeStrategy = MergeStrategy.RECURSIVE) -> Tuple[bool, Optional[str]]`
Attempt automatic merge conflict resolution.

#### `abort_merge() -> bool`
Abort an in-progress merge.

#### `create_tag(version: str, message: Optional[str] = None, annotated: bool = True) -> bool`
Create a Git tag with semantic versioning.

#### `get_latest_tag() -> Optional[str]`
Get the most recent tag.

#### `get_commit_history(limit: int = 10) -> List[Dict[str, str]]`
Get recent commit history.

## Support

For issues or questions about Git integration:

1. Check the test suite: `tests/test_git_manager.py`
2. Run the demo: `examples/git_integration_demo.py`
3. Review the source: `src/foundry/vcs/git_manager.py`
