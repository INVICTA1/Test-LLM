"""SWE-bench data point validator"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
import click


def load_data_points(data_points_dir):
    """Load all JSON data points from directory"""
    data_points = []
    for json_file in sorted(Path(data_points_dir).glob("*.json")):
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
def main(data_points_dir, instance_id, max_workers, timeout):
    """Validate SWE-bench data points using golden patches"""
    
    # Load all data points
    all_data_points = load_data_points(data_points_dir)
    
    if not all_data_points:
        click.echo("No data points found", err=True)
        sys.exit(1)
    
    # Filter by instance_id if specified
    if instance_id:
        instance_ids = set(instance_id)
        data_points = [dp for dp in all_data_points if dp["instance_id"] in instance_ids]
    else:
        data_points = all_data_points
    
    if not data_points:
        click.echo("No matching instances found", err=True)
        sys.exit(1)
    
    click.echo(f"Validating {len(data_points)} instance(s)")
    
    # Create temporary files for dataset and predictions
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
        # Run SWE-bench evaluation with local dataset
        cmd = [
            "python", "-m", "swebench.harness.run_evaluation",
            "--dataset_name", dataset_file,
            "--predictions_path", predictions_file,
            "--max_workers", str(max_workers),
            "--timeout", str(timeout),
            "--run_id", "validation",
        ]
        
        click.echo(f"Running evaluation...")
        result = subprocess.run(cmd)
        sys.exit(result.returncode)
        
    finally:
        Path(dataset_file).unlink(missing_ok=True)
        Path(predictions_file).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
