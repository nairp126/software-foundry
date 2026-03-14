# Database Migration Root Cause Analysis

## Date: 2026-03-13

## Summary
Successfully identified and fixed both the database migration failures and test infrastructure issues. All tests now pass with proper data isolation.

## Root Causes Identified and Fixed

### 1. Alembic Configuration Issue (FIXED ✅)
**Problem**: The `alembic/env.py` file was unconditionally overriding the `sqlalchemy.url` configuration with `settings.database_url` (which points to the main database).

**Location**: `alembic/env.py` line 20

**Original Code**:
```python
config.set_main_option("sqlalchemy.url", settings.database_url)
```

**Impact**: When tests tried to run migrations on the test database by setting the URL to `foundry_db_test`, Alembic would ignore it and always connect to the main database (`foundry_db`). This caused:
- Migrations to appear successful but not actually run on the test database
- Test database to remain empty (no tables created)
- All tests to fail with "relation does not exist" errors

**Fix Applied**:
```python
# Override sqlalchemy.url with our database URL only if not already set
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", settings.database_url)
```

**Result**: Migrations now run successfully on the test database. All tables and enum types are created correctly.

### 2. Test Infrastructure Issues (FIXED ✅)

#### Problem
Tests were failing with connection pool errors:
- `InterfaceError: cannot perform operation: another operation is in progress`
- Tests finding leftover data from previous runs
- Data not properly isolated between tests

#### Root Cause
API endpoints were creating their own database sessions using `AsyncSessionLocal()` directly instead of using dependency injection. This meant:
1. Test fixtures couldn't override the database session
2. Multiple connections were being used, causing transaction conflicts
3. Data wasn't being properly isolated between tests

#### Solution
Modified all API key endpoints to use FastAPI's dependency injection pattern:

**Before:**
```python
@app.post("/api-keys")
async def create_api_key(request: APIKeyCreateRequest):
    async with AsyncSessionLocal() as session:
        session.add(api_key)
        await session.commit()
```

**After:**
```python
@app.post("/api-keys")
async def create_api_key(
    request: APIKeyCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    db.add(api_key)
    await db.commit()
```

#### Changes Made
1. **src/foundry/main.py**:
   - Added `AsyncSession` import from `sqlalchemy.ext.asyncio`
   - Added `get_db` to imports from `foundry.database`
   - Modified 4 endpoints to use dependency injection:
     - `POST /api-keys` - create_api_key
     - `GET /api-keys` - list_api_keys
     - `DELETE /api-keys/{key_id}` - delete_api_key
     - `PATCH /api-keys/{key_id}/deactivate` - deactivate_api_key

2. **tests/conftest.py**:
   - Simplified test fixtures to use transaction rollback pattern
   - Each test runs in its own transaction that gets rolled back
   - Proper session cleanup in finally block

#### Benefits
1. **Test Isolation**: Tests can now override `get_db` to provide a session within a transaction that gets rolled back
2. **No Connection Conflicts**: All operations use the same session/connection during tests
3. **Cleaner Code**: Follows FastAPI best practices for dependency injection
4. **Better Testability**: Easier to mock and test database operations

## Verification

### Main Database Status
```bash
$ python -m alembic current
460bc123d457 (head)
```
✅ Main database is at the latest migration

### Test Database Status
```bash
$ python check_test_db.py
Tables in test database:
  - alembic_version
  - artifacts
  - approval_requests
  - projects
  - api_keys

Enum types in test database:
  - project_status
  - artifact_type
  - approval_status
  - approval_type
  - approval_policy
```
✅ Test database has all required tables and enum types

### Test Results
```bash
$ python -m pytest tests/test_api_authentication.py -v
======================= 15 passed, 87 warnings in 0.47s =======================
```
✅ All 15 tests passing (10 model tests + 5 endpoint tests)

## Files Modified

1. **alembic/env.py** - Fixed database URL override logic (line 20)
2. **src/foundry/main.py** - Converted API endpoints to use dependency injection
3. **tests/conftest.py** - Simplified test fixtures with transaction rollback pattern

## Impact

- ✅ Tests now run reliably with proper data isolation
- ✅ No more connection pool errors
- ✅ Test database properly separated from main database
- ✅ Follows FastAPI best practices for dependency injection
- ✅ Easier to maintain and extend test suite

## Conclusion

Both the migration issue and test infrastructure problems have been fully resolved. The test database now has all required tables, migrations run correctly, and all tests pass with proper isolation. The codebase now follows FastAPI best practices for database session management.
