# SWE-bench Data Point Validator

Infrastructure for validating SWE-bench data points using Docker-based evaluation.

## Quick Start

### Prerequisites
- Docker
- Python 3.10+
- 120GB+ free disk space

### Setup

**Option 1: Docker (Recommended)**
```bash
# Build image
docker-compose build

# Run validator
docker-compose --profile validator run --rm validator \
  python -m swe_bench_validator data_points --instance-id "astropy__astropy-11693"
```

**Option 2: Local**
```bash
cd task-release-2025-07-29-115124

# Install UV
pip install uv

# Install dependencies
uv venv
uv pip install -e .

# Run validator
source .venv/bin/activate
python -m swe_bench_validator data_points --instance-id "django__django-10087"
```

## Usage

### Validate Specific Instances
```bash
python -m swe_bench_validator data_points \
  --instance-id "astropy__astropy-11693" \
  --instance-id "django__django-10087" \
  --max-workers 2 \
  --timeout 1800
```

### Validate All Data Points
```bash
python -m swe_bench_validator data_points --max-workers 2
```

### Options
- `--instance-id` - Specific instance to validate (can specify multiple)
- `--max-workers` - Number of parallel workers (default: 1)
- `--timeout` - Timeout per instance in seconds (default: 900)

## Data Point Format

### Valid Data Point Example
```json
{
  "instance_id": "django__django-10087",
  "repo": "django/django",
  "base_commit": "02cd16a7a04529c726e5bb5a13d5979119f25c7d",
  "patch": "diff --git a/django/core/...",
  "test_patch": "diff --git a/tests/...",
  "FAIL_TO_PASS": ["tests.migrations.test_commands::test_sqlmigrate_nonexistent_app_label"],
  "PASS_TO_PASS": ["tests.migrations.test_commands::test_migrate"]
}
```

### Invalid Data Point Examples

**1. Patch Fails to Apply**
```json
{
  "instance_id": "example-fail-patch",
  "patch": "diff --git a/nonexistent/file.py ..."  // Wrong file path
}
```

**2. Tests Still Fail After Patch**
```json
{
  "instance_id": "example-fail-tests",
  "patch": "diff --git a/code.py ...",  // Incomplete fix
  "FAIL_TO_PASS": ["test_feature"]  // Will still fail
}
```

**3. Breaks Existing Tests**
```json
{
  "instance_id": "example-break-tests",
  "patch": "diff --git a/code.py ...",  // Introduces bug
  "PASS_TO_PASS": ["test_existing"]  // Will now fail
}
```

## GitHub Action

Automatically validates data points on PR/push:

```yaml
# .github/workflows/validate-datapoints.yml
- Triggers on changes to data_points/**/*.json
- Validates only changed files
- Reports status as green ✅ or red ❌
```

## Project Structure

```
.
├── swe-bench-docker-architecture.md   # Docker architecture docs
├── README.md                          # This file
├── Dockerfile                         # Docker image
├── docker-compose.yml                 # Services configuration
├── .github/
│   └── workflows/
│       └── validate-datapoints.yml    # CI/CD workflow
└── task-release-2025-07-29-115124/
    ├── swe_bench_validator/           # Validator module
    │   ├── __init__.py
    │   ├── __main__.py
    │   └── validator.py
    ├── swe_bench_downloader/          # Downloader module
    ├── data_points/                   # Data point files
    │   ├── astropy__astropy-11693.json       # Valid example
    │   ├── django__django-10087.json         # Valid example
    │   └── astropy__astropy-11693-fail.json  # Invalid example
    └── pyproject.toml                 # Dependencies
```

## How It Works

1. **Load Data Points** - Read JSON files from `data_points/`
2. **Convert Format** - Transform to SWE-bench predictions format
3. **Run Evaluation** - Use `swebench.harness.run_evaluation`
4. **Check Results** - Verify FAIL_TO_PASS and PASS_TO_PASS tests
5. **Report** - Show resolved/unresolved/errors

See [swe-bench-docker-architecture.md](swe-bench-docker-architecture.md) for detailed Docker workflow.

## Examples

### Valid: astropy__astropy-11693
- **Issue**: WCS convergence error during plotting
- **Fix**: Catch NoConvergence exception, use best_solution
- **Result**: ✅ FAIL_TO_PASS tests now pass

### Valid: django__django-10087  
- **Issue**: Misleading sqlmigrate error message
- **Fix**: Add app_label validation
- **Result**: ✅ FAIL_TO_PASS tests now pass

### Invalid: astropy__astropy-11693-fail
- **Issue**: Same as above but incomplete fix
- **Result**: ❌ Docker image not found (test file)

## Troubleshooting

### Validation Fails
```bash
# Check logs
docker logs <container_id>

# Clean up old containers
docker ps -a | grep sweb.eval | awk '{print $1}' | xargs docker rm -f

# Clean up images
docker system prune -a
```

### Out of Disk Space
```bash
# Check usage
docker system df

# Remove unused images
docker image prune -a

# Use env cache level (recommended)
--cache_level env  # ~100GB vs 2TB for instance level
```

### Permission Errors
```bash
# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

## Development

### With Docker Volumes (Fast)
Code is mounted via volumes - changes apply immediately without rebuild:

```bash
# Edit code
vim task-release-2025-07-29-115124/swe_bench_validator/validator.py

# Run immediately (no rebuild!)
docker-compose --profile validator run --rm validator \
  python -m swe_bench_validator data_points
```

### Without Docker
```bash
cd task-release-2025-07-29-115124
source .venv/bin/activate

# Edit and run
vim swe_bench_validator/validator.py
python -m swe_bench_validator data_points
```

## License

This is a test assignment for infrastructure development evaluation.

