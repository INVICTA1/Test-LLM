# SWE-bench Docker Architecture

## Overview

SWE-bench uses a 3-layer Docker architecture to create isolated, reproducible test environments for validating code patches.

```
Base Image → Environment Image → Instance Image
```

## 1. Three-Layer Docker System

### Layer 1: Base Image
- **Purpose**: Common foundation for all evaluations
- **Contains**: Python runtime, system dependencies, git
- **Example**: `ubuntu:22.04` with Python 3.10
- **Built**: Once per Python version
- **Cached**: Yes, shared across all instances

### Layer 2: Environment Image
- **Purpose**: Repository-specific dependencies
- **Contains**: Project dependencies (requirements.txt, setup.py)
- **Example**: For `django/django` - installs Django dependencies
- **Built**: Once per repository version
- **Cached**: Yes, shared across instances from same repo
- **Size**: ~1-2GB per repository

### Layer 3: Instance Image
- **Purpose**: Specific test case setup
- **Contains**: 
  - Repository cloned at `base_commit`
  - Test patch applied (`test_patch`)
  - Ready to apply solution patch
- **Example**: `django__django-10087` at specific commit
- **Built**: Per instance
- **Cached**: Optional (can be 2TB+ for all instances)

## 2. Image Building Process

### When Images Are Built

```python
# Triggered by: swebench.harness.run_evaluation

1. Check if Base image exists → Build if missing
2. Check if Environment image exists → Build if missing  
3. Build Instance image (always fresh or cached)
```

### Build Steps

**Base Image:**
```dockerfile
FROM ubuntu:22.04
RUN apt-get update && apt-get install python3.10 git
```

**Environment Image:**
```dockerfile
FROM base_image
COPY requirements.txt .
RUN pip install -r requirements.txt
```

**Instance Image:**
```dockerfile
FROM env_image
RUN git clone <repo> && git checkout <base_commit>
RUN git apply test_patch.diff  # Add tests
```

### Where Dependencies Are Installed

1. **System packages** → Base image
2. **Python dependencies** → Environment image (from repo's requirements)
3. **Test requirements** → Environment image
4. **Repository code** → Instance image

## 3. Test Execution Flow

### Step-by-Step Process

```
1. Build/Pull Instance Image
2. Create Container from Instance Image
3. Apply Solution Patch (golden patch)
4. Run Tests
5. Parse Results
6. Cleanup
```

### Detailed Execution

**1. Apply Patch:**
```bash
cd /testbed
git apply --check solution.patch  # Verify patch applies
git apply solution.patch           # Apply the fix
```

**2. Run Tests:**
```bash
# Execute test command with timeout
timeout 1800s python -m pytest <test_paths>
```

**3. Parse Results:**
- Capture stdout/stderr
- Extract test outcomes (PASSED/FAILED)
- Match against `FAIL_TO_PASS` and `PASS_TO_PASS`
- Determine: RESOLVED / UNRESOLVED / ERROR

**4. Timeout Handling:**
- Default: 900s (15 min) per instance
- Configurable via `--timeout` flag
- On timeout: mark as ERROR, container killed

## 4. Concrete Example

### Django Instance: `django__django-10087`

**Data Point:**
```json
{
  "instance_id": "django__django-10087",
  "repo": "django/django",
  "base_commit": "02cd16a7...",
  "patch": "diff --git a/django/core/...",
  "FAIL_TO_PASS": ["tests.migrations.test_commands::test_sqlmigrate_nonexistent_app_label"],
  "PASS_TO_PASS": ["tests.migrations.test_commands::test_migrate"]
}
```

**Execution:**

1. **Build Environment** (cached):
   ```bash
   FROM python:3.10
   RUN git clone django/django
   RUN pip install -e .[test]
   ```

2. **Build Instance**:
   ```bash
   RUN git checkout 02cd16a7...
   RUN git apply test_patch.diff
   ```

3. **Apply Solution**:
   ```bash
   git apply solution.patch
   # Adds validation to sqlmigrate command
   ```

4. **Run Tests**:
   ```bash
   ./tests/runtests.py migrations.test_commands::test_sqlmigrate_nonexistent_app_label
   # Expected: PASS (was failing before patch)
   
   ./tests/runtests.py migrations.test_commands::test_migrate  
   # Expected: PASS (should stay passing)
   ```

5. **Result**:
   - `FAIL_TO_PASS`: ✅ Now passes → RESOLVED
   - `PASS_TO_PASS`: ✅ Still passes → Good

## 5. Integration with Validator

### How Validator Uses Docker

**Our validator** (`swe_bench_validator`):

```python
1. Load data points from JSON files
2. Convert to predictions format (patch → model_patch)
3. Call swebench.harness.run_evaluation
4. SWE-bench handles all Docker operations
5. Return results (resolved/unresolved/errors)
```

**Docker Operations (by SWE-bench):**
- Image building (3 layers)
- Container creation
- Patch application
- Test execution
- Result parsing
- Cleanup

**Validator doesn't directly interact with Docker** - delegates to SWE-bench harness.

### Docker Requirements

**For Validator:**
- Docker daemon running
- Access to Docker socket (`/var/run/docker.sock`)
- Sufficient disk space (~120GB minimum)
- Sufficient memory (~4GB per worker)

**In docker-compose.yml:**
```yaml
validator:
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock  # Docker-in-Docker
  privileged: true  # Required for Docker operations
```

## 6. Performance & Caching

### Cache Levels

```bash
--cache_level none     # No cache, rebuild all (~120GB)
--cache_level base     # Cache base images only (~120GB)
--cache_level env      # Cache base + env (recommended, ~100GB)
--cache_level instance # Cache everything (~2TB)
```

### Optimization

1. **Use `env` cache** - balances speed vs disk
2. **Parallel workers** - run multiple instances simultaneously
3. **Local dataset** - avoid HuggingFace downloads
4. **Cleanup old images** - `docker system prune`

## 7. Error Handling

### Common Issues

**1. Image Build Failure:**
- Missing dependencies in requirements
- Network issues during git clone
- Incompatible Python version

**2. Patch Application Failure:**
- Patch doesn't apply cleanly to base_commit
- File paths incorrect
- Merge conflicts

**3. Test Execution Failure:**
- Tests timeout (>900s default)
- Missing test dependencies
- Environment issues

**4. Container Issues:**
- Name conflicts (old containers not removed)
- Out of disk space
- Permission errors

### Debugging

```bash
# Check logs
cat logs/run_evaluation/validation/gold/<instance_id>/run_instance.log

# Inspect container
docker ps -a | grep sweb.eval
docker logs <container_id>

# Check images
docker images | grep swebench
```

## Summary

**3 Layers:** Base (system) → Environment (dependencies) → Instance (test setup)

**Build Process:** Check cache → Build missing layers → Ready for test

**Test Flow:** Apply patch → Run tests → Parse results → Cleanup

**Integration:** Validator → SWE-bench → Docker → Results

**Cache Strategy:** Use `env` level for best performance/space balance

