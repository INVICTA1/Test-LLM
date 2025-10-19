"""SWE-bench data point validator"""

import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path
import click

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def validate_data_point_structure(data):
    """Validate that data point has required fields"""
    required_fields = ["instance_id", "repo", "patch", "base_commit"]
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        raise ValueError(f"Missing required fields: {missing_fields}")
    return True

def load_data_points(data_points_dir):
    """Load JSON data points from directory"""
    data_points = []
    for json_file in Path(data_points_dir).glob("*.json"):
        try:
            with open(json_file) as f:
                data = json.load(f)
                validate_data_point_structure(data)
                data_points.append(data)
                logger.info(f"Loaded data point: {data.get('instance_id', 'unknown')}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {json_file}: {e}")
            click.echo(f"Error loading {json_file}: Invalid JSON format", err=True)
        except ValueError as e:
            logger.error(f"Invalid data point structure in {json_file}: {e}")
            click.echo(f"Error loading {json_file}: {e}", err=True)
        except Exception as e:
            logger.error(f"Unexpected error loading {json_file}: {e}")
            click.echo(f"Error loading {json_file}: {e}", err=True)
    return data_points


@click.command()
@click.argument('data_points_dir', type=click.Path(exists=True))
@click.option('--instance-id', multiple=True, help='Validate specific instance(s)')
@click.option('--max-workers', default=1, type=int, help='Parallel workers')
@click.option('--timeout', default=900, type=int, help='Timeout per instance (seconds)')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
def main(data_points_dir, instance_id, max_workers, timeout, verbose):
    """Validate SWE-bench data points using golden patches"""
    
    # Load and filter data points
    all_data_points = load_data_points(data_points_dir)
    if not all_data_points:
        click.echo("No data points found", err=True)
        sys.exit(1)
    
    if instance_id:
        instance_ids = set(instance_id)
        data_points = [dp for dp in all_data_points if dp["instance_id"] in instance_ids]
    else:
        data_points = all_data_points
    
    if not data_points:
        click.echo("No matching instances found", err=True)
        sys.exit(1)
    
    click.echo(f"Validating {len(data_points)} instance(s)")
    if verbose:
        for dp in data_points:
            click.echo(f"  - {dp['instance_id']} ({dp.get('repo', 'unknown')})")
    
    # Create temporary files
    dataset_file = None
    predictions_file = None
    
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as df:
            for dp in data_points:
                df.write(json.dumps(dp) + '\n')
            dataset_file = df.name
            logger.info(f"Created dataset file: {dataset_file}")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as pf:
            for dp in data_points:
                pred = {
                    "instance_id": dp["instance_id"],
                    "model_patch": dp["patch"],
                    "model_name_or_path": "gold"
                }
                pf.write(json.dumps(pred) + '\n')
            predictions_file = pf.name
            logger.info(f"Created predictions file: {predictions_file}")
    except Exception as e:
        logger.error(f"Failed to create temporary files: {e}")
        click.echo(f"❌ Failed to create temporary files: {e}", err=True)
        sys.exit(1)
    
    try:
        # Run SWE-bench evaluation
        cmd = [
            "python", "-m", "swebench.harness.run_evaluation",
            "--dataset_name", dataset_file,
            "--predictions_path", predictions_file,
            "--max_workers", str(max_workers),
            "--timeout", str(timeout),
            "--run_id", "validation",
        ]
        
        click.echo("Running evaluation...")
        if verbose:
            click.echo(f"Command: {' '.join(cmd)}")
        
        logger.info(f"Running SWE-bench evaluation for {len(data_points)} data points")
        result = subprocess.run(cmd, capture_output=True, text=True)
        logger.info(f"SWE-bench evaluation completed with exit code: {result.returncode}")
        
        # Check if the command failed
        if result.returncode != 0:
            logger.error(f"SWE-bench evaluation failed with exit code {result.returncode}")
            click.echo(f"\n❌ Validation failed: SWE-bench evaluation exited with code {result.returncode}")
            if verbose and (result.stdout or result.stderr):
                click.echo(f"\nSTDOUT: {result.stdout}")
                click.echo(f"STDERR: {result.stderr}")
            sys.exit(1)
        
        # Parse results from logs
        logs_dir = Path("logs/run_evaluation/validation/gold")
        resolved = 0
        unresolved = 0
        errors = 0
        
        logger.info(f"Parsing results from logs directory: {logs_dir}")
        
        for result_file in logs_dir.glob("**/results.jsonl"):
            try:
                logger.info(f"Processing result file: {result_file}")
                with open(result_file) as f:
                    for line in f:
                        if line.strip():
                            result_data = json.loads(line)
                            status = result_data.get("status", "unknown")
                            instance_id = result_data.get("instance_id", "unknown")
                            logger.info(f"Instance {instance_id}: {status}")
                            if status == "RESOLVED":
                                resolved += 1
                            elif status == "UNRESOLVED":
                                unresolved += 1
                            else:
                                errors += 1
            except Exception as e:
                logger.error(f"Error processing result file {result_file}: {e}")
                pass
        
        # Display results
        logger.info(f"Validation results: {resolved} resolved, {unresolved} unresolved, {errors} errors")
        click.echo(f"\nResults: ✅ {resolved} resolved, ❌ {unresolved} unresolved, 🚨 {errors} errors")
        
        if verbose and (result.stdout or result.stderr):
            click.echo(f"\nSTDOUT: {result.stdout}")
            click.echo(f"STDERR: {result.stderr}")
        
        # Exit with appropriate code
        if unresolved > 0 or errors > 0:
            logger.error(f"Validation failed: {unresolved} unresolved, {errors} errors")
            click.echo(f"\n❌ Validation failed: {unresolved} unresolved, {errors} errors")
            sys.exit(1)
        else:
            logger.info("All validations passed successfully")
            click.echo(f"\n✅ All validations passed!")
            sys.exit(0)
        
    except Exception as e:
        logger.error(f"Validation error: {e}")
        click.echo(f"❌ Validation error: {e}", err=True)
        if verbose:
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            click.echo(traceback.format_exc(), err=True)
        sys.exit(1)
        
    finally:
        # Clean up temporary files
        try:
            if dataset_file and Path(dataset_file).exists():
                Path(dataset_file).unlink()
                logger.info(f"Cleaned up dataset file: {dataset_file}")
            if predictions_file and Path(predictions_file).exists():
                Path(predictions_file).unlink()
                logger.info(f"Cleaned up predictions file: {predictions_file}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary files: {e}")


if __name__ == "__main__":
    main()
