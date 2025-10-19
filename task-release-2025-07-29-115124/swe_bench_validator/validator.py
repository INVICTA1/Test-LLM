"""SWE-bench data point validator"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
import click


def load_data_points(data_points_dir):
    """Load JSON data points from directory"""
    data_points = []
    for json_file in Path(data_points_dir).glob("*.json"):
        try:
            with open(json_file) as f:
                data = json.load(f)
                if "instance_id" in data and "patch" in data:
                    data_points.append(data)
        except Exception as e:
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
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as df:
        for dp in data_points:
            df.write(json.dumps(dp) + '\n')
        dataset_file = df.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as pf:
        for dp in data_points:
            pred = {
                "instance_id": dp["instance_id"],
                "model_patch": dp["patch"],
                "model_name_or_path": "gold"
            }
            pf.write(json.dumps(pred) + '\n')
        predictions_file = pf.name
    
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
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Parse results from logs
        logs_dir = Path("logs/run_evaluation/validation/gold")
        resolved = 0
        unresolved = 0
        errors = 0
        
        for result_file in logs_dir.glob("**/results.jsonl"):
            try:
                with open(result_file) as f:
                    for line in f:
                        if line.strip():
                            result_data = json.loads(line)
                            status = result_data.get("status", "unknown")
                            if status == "RESOLVED":
                                resolved += 1
                            elif status == "UNRESOLVED":
                                unresolved += 1
                            else:
                                errors += 1
            except Exception:
                pass
        
        # Display results
        click.echo(f"\nResults: ✅ {resolved} resolved, ❌ {unresolved} unresolved, 🚨 {errors} errors")
        
        if verbose and (result.stdout or result.stderr):
            click.echo(f"\nSTDOUT: {result.stdout}")
            click.echo(f"STDERR: {result.stderr}")
        
        # Exit with appropriate code
        if unresolved > 0 or errors > 0:
            click.echo(f"\n❌ Validation failed: {unresolved} unresolved, {errors} errors")
            sys.exit(1)
        else:
            click.echo(f"\n✅ All validations passed!")
            sys.exit(0)
        
    except Exception as e:
        click.echo(f"❌ Validation error: {e}", err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc(), err=True)
        sys.exit(1)
        
    finally:
        Path(dataset_file).unlink(missing_ok=True)
        Path(predictions_file).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
