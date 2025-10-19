"""Enhanced SWE-bench data point validator with modular architecture"""

import logging
import sys
from pathlib import Path
import click

from .enhanced_validator import EnhancedValidator

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@click.command()
@click.argument('data_points_dir', type=click.Path(exists=True))
@click.option('--instance-id', multiple=True, help='Validate specific instance(s)')
@click.option('--max-workers', default=1, type=int, help='Parallel workers')
@click.option('--timeout', default=900, type=int, help='Timeout per instance (seconds)')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.option('--model-name', default='gold', help='Model name for predictions')
def main(data_points_dir, instance_id, max_workers, timeout, verbose, model_name):
    """Enhanced SWE-bench data point validator with modular architecture"""
    
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize enhanced validator
    validator = EnhancedValidator(data_dir=data_points_dir, model_name=model_name)
    
    # Prepare files to validate
    files_to_validate = None
    if instance_id:
        # Convert instance IDs to file names (assuming instance_id matches filename)
        files_to_validate = list(instance_id)
        click.echo(f"Validating specific instances: {', '.join(instance_id)}")
    else:
        click.echo("Validating all data points in directory")
    
    # Run validation
    try:
        results = validator.validate(
            files=files_to_validate,
            max_workers=max_workers,
            timeout=timeout,
            verbose=verbose
        )
        
        # Display results
        validator.display_results(results)
        
        # Generate summary report for GitHub Actions
        if verbose:
            summary_report = validator.get_summary_report(results)
            click.echo(f"\n📋 Summary Report:\n{summary_report}")
        
        # Exit with appropriate code
        if results.get("success", False):
            click.echo("\n🎉 Validation completed successfully!")
            sys.exit(0)
        else:
            error_msg = results.get("error", "Validation failed")
            click.echo(f"\n❌ Validation failed: {error_msg}")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Unexpected error during validation: {e}")
        click.echo(f"❌ Unexpected error: {e}", err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc(), err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()