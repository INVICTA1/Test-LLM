"""
Enhanced SWE-bench validator with modular architecture, comprehensive validation,
detailed statistics, and improved error handling.
"""

import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional

from .data_point_reader import DataPointReader
from .prediction_converter import PredictionConverter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnhancedValidator:
    """
    Enhanced SWE-bench validator with modular architecture and comprehensive features.
    """
    
    def __init__(self, data_dir: str = "data_points", model_name: str = "gold"):
        """
        Initialize the enhanced validator.
        
        Args:
            data_dir: Directory containing data point JSON files
            model_name: Model name for predictions (default: "gold" for golden patches)
        """
        self.data_dir = Path(data_dir)
        self.model_name = model_name
        self.loader = DataPointReader()
        self.converter = PredictionConverter(model_name=model_name)
        
        logger.info(f"Initialized EnhancedValidator with data_dir: {data_dir}, model: {model_name}")
    
    def validate(self, files: Optional[List[str]] = None, max_workers: int = 1, 
                timeout: int = 900, verbose: bool = False, 
                show_validation_errors: bool = True) -> Dict[str, Any]:
        """
        Validate SWE-bench data points with comprehensive reporting.
        
        Args:
            files: Optional list of specific file names to validate
            max_workers: Number of parallel workers
            timeout: Timeout per instance in seconds
            verbose: Enable verbose output
            
        Returns:
            Comprehensive validation results
        """
        try:
            logger.info(f"Starting validation with {len(files) if files else 'all'} files")
            
            # Load data points
            data_points = self.loader.load(self.data_dir, files)
            
            # If no valid data points but we want to show validation errors
            if not data_points and show_validation_errors:
                validation_errors = self._get_validation_errors(self.data_dir, files)
                return {
                    "success": False,
                    "error": "No valid data points found for validation",
                    "validation_errors": validation_errors,
                    "statistics": {"total": 0, "valid": 0, "invalid": len(validation_errors), "success_rate": 0.0}
                }
            elif not data_points:
                return {
                    "success": False,
                    "error": "No data points found for validation",
                    "statistics": {"total": 0, "valid": 0, "invalid": 0, "success_rate": 0.0}
                }
            
            # Get validation summary
            validation_summary = self.loader.get_validation_summary(data_points)
            
            # Convert to predictions
            predictions = self.converter.convert(data_points)
            if not predictions:
                return {
                    "success": False,
                    "error": "Failed to convert data points to predictions",
                    "statistics": validation_summary
                }
            
            # Create temporary files
            dataset_file, predictions_file = self._create_temp_files(data_points, predictions)
            if not dataset_file or not predictions_file:
                return {
                    "success": False,
                    "error": "Failed to create temporary files",
                    "statistics": validation_summary
                }
            
            try:
                # Run SWE-bench evaluation
                evaluation_result = self._run_evaluation(
                    dataset_file, predictions_file, max_workers, timeout, verbose
                )
                
                # Parse results
                results = self._parse_results(data_points, verbose)
                
                # Combine all results - validation fails if SWE-bench evaluation fails
                final_results = {
                    "success": evaluation_result["success"],
                    "statistics": validation_summary,
                    "evaluation": evaluation_result,
                    "validation_results": results,
                    "data_points_processed": len(data_points),
                    "predictions_created": len(predictions)
                }
                
                # Add error details if evaluation failed
                if not evaluation_result["success"]:
                    final_results["error"] = "SWE-bench evaluation failed"
                    if "error_details" in evaluation_result:
                        final_results["error_details"] = evaluation_result["error_details"]
                
                return final_results
                
            finally:
                # Clean up temporary files
                self._cleanup_temp_files(dataset_file, predictions_file)
                
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return {
                "success": False,
                "error": str(e),
                "statistics": {"total": 0, "valid": 0, "invalid": 0, "success_rate": 0.0}
            }
    
    def _create_temp_files(self, data_points: List[Dict[str, Any]], 
                          predictions: List[Dict[str, str]]) -> tuple[Optional[str], Optional[str]]:
        """Create temporary files for SWE-bench evaluation."""
        try:
            # Create dataset file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as df:
                for dp in data_points:
                    df.write(json.dumps(dp) + '\n')
                dataset_file = df.name
                logger.info(f"Created dataset file: {dataset_file}")
            
            # Create predictions file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as pf:
                for pred in predictions:
                    pf.write(json.dumps(pred) + '\n')
                predictions_file = pf.name
                logger.info(f"Created predictions file: {predictions_file}")
            
            return dataset_file, predictions_file
            
        except Exception as e:
            logger.error(f"Failed to create temporary files: {e}")
            return None, None
    
    def _run_evaluation(self, dataset_file: str, predictions_file: str, 
                       max_workers: int, timeout: int, verbose: bool) -> Dict[str, Any]:
        """Run SWE-bench evaluation."""
        cmd = [
            "python", "-m", "swebench.harness.run_evaluation",
            "--dataset_name", dataset_file,
            "--predictions_path", predictions_file,
            "--max_workers", str(max_workers),
            "--timeout", str(timeout),
            "--run_id", "validation",
        ]
        
        logger.info("Running SWE-bench evaluation...")
        if verbose:
            logger.info(f"Command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 300)
            
            evaluation_result = {
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": cmd
            }
            
            if result.returncode != 0:
                logger.error(f"SWE-bench evaluation failed with exit code {result.returncode}")
                if verbose:
                    logger.error(f"STDOUT: {result.stdout}")
                    logger.error(f"STDERR: {result.stderr}")
                
                # Try to extract specific error information
                error_info = self._extract_error_info(result.stderr)
                evaluation_result["error_details"] = error_info
            else:
                logger.info("SWE-bench evaluation completed successfully")
            
            return evaluation_result
            
        except subprocess.TimeoutExpired:
            logger.error("SWE-bench evaluation timed out")
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": "Evaluation timed out",
                "command": cmd
            }
        except Exception as e:
            logger.error(f"Error running SWE-bench evaluation: {e}")
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "command": cmd
            }
    
    def _parse_results(self, data_points: List[Dict[str, Any]], verbose: bool) -> Dict[str, Any]:
        """Parse validation results from logs."""
        logs_dir = Path("logs/run_evaluation/validation/gold")
        resolved = 0
        unresolved = 0
        errors = 0
        detailed_results = []
        
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
                            
                            if verbose:
                                logger.info(f"Instance {instance_id}: {status}")
                            
                            detailed_results.append({
                                "instance_id": instance_id,
                                "status": status,
                                "result_data": result_data
                            })
                            
                            if status == "RESOLVED":
                                resolved += 1
                            elif status == "UNRESOLVED":
                                unresolved += 1
                            else:
                                errors += 1
                                
            except Exception as e:
                logger.error(f"Error processing result file {result_file}: {e}")
        
        return {
            "success": unresolved == 0 and errors == 0,
            "resolved": resolved,
            "unresolved": unresolved,
            "errors": errors,
            "detailed_results": detailed_results,
            "total_instances": len(data_points)
        }
    
    def _get_validation_errors(self, data_dir: Path, files: Optional[List[str]]) -> List[Dict[str, Any]]:
        """Get detailed validation errors for all files."""
        validation_errors = []
        
        if files is None:
            json_files = list(data_dir.glob("*.json"))
        else:
            json_files = []
            for file in files:
                if not file.endswith('.json'):
                    file = file + '.json'
                file_path = data_dir / file
                if file_path.exists():
                    json_files.append(file_path)
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data_point = json.load(f)
                
                validation_result = self.loader._validate_comprehensive(data_point, json_file.name)
                
                if not validation_result["valid"]:
                    validation_errors.append({
                        "file": json_file.name,
                        "instance_id": data_point.get("instance_id", "unknown"),
                        "errors": validation_result["errors"],
                        "warnings": validation_result["warnings"]
                    })
                    
            except Exception as e:
                validation_errors.append({
                    "file": json_file.name,
                    "instance_id": "unknown",
                    "errors": [f"Failed to load file: {str(e)}"],
                    "warnings": []
                })
        
        return validation_errors
    
    def _extract_error_info(self, stderr: str) -> Dict[str, Any]:
        """Extract specific error information from stderr."""
        error_info = {
            "type": "unknown",
            "message": "Unknown error",
            "details": stderr
        }
        
        if "KeyError:" in stderr:
            # Extract repository name from KeyError
            import re
            match = re.search(r"KeyError: '([^']+)'", stderr)
            if match:
                repo = match.group(1)
                error_info.update({
                    "type": "unknown_repository",
                    "message": f"Unknown repository: {repo}",
                    "repository": repo,
                    "suggestion": "Use a supported repository like 'astropy/astropy' or 'django/django'"
                })
        elif "TimeoutExpired" in stderr:
            error_info.update({
                "type": "timeout",
                "message": "Evaluation timed out",
                "suggestion": "Increase timeout or check for infinite loops"
            })
        elif "Docker" in stderr and "error" in stderr.lower():
            error_info.update({
                "type": "docker_error",
                "message": "Docker execution error",
                "suggestion": "Check Docker installation and permissions"
            })
        
        return error_info
    
    def _cleanup_temp_files(self, dataset_file: Optional[str], predictions_file: Optional[str]):
        """Clean up temporary files."""
        try:
            if dataset_file and Path(dataset_file).exists():
                Path(dataset_file).unlink()
                logger.info(f"Cleaned up dataset file: {dataset_file}")
            if predictions_file and Path(predictions_file).exists():
                Path(predictions_file).unlink()
                logger.info(f"Cleaned up predictions file: {predictions_file}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary files: {e}")
    
    def display_results(self, results: Dict[str, Any]) -> None:
        """Display comprehensive validation results."""
        print("\n" + "="*80)
        print("🔍 SWE-bench Enhanced Validation Results")
        print("="*80)
        
        if not results.get("success", False):
            print(f"❌ Validation failed: {results.get('error', 'Unknown error')}")
            
            # Display validation errors if available
            validation_errors = results.get("validation_errors", [])
            if validation_errors:
                print(f"\n🔍 Data Point Validation Errors:")
                for error in validation_errors:
                    print(f"\n📄 File: {error['file']}")
                    print(f"   Instance ID: {error['instance_id']}")
                    print(f"   Errors: {len(error['errors'])}")
                    for i, err in enumerate(error['errors'], 1):
                        print(f"     {i}. {err}")
                    if error['warnings']:
                        print(f"   Warnings: {len(error['warnings'])}")
                        for i, warn in enumerate(error['warnings'], 1):
                            print(f"     {i}. {warn}")
            
            # Display detailed error information
            eval_results = results.get("evaluation", {})
            if eval_results.get("error_details"):
                error_details = eval_results["error_details"]
                print(f"\n🔍 Error Analysis:")
                print(f"   Type: {error_details.get('type', 'unknown')}")
                print(f"   Message: {error_details.get('message', 'Unknown error')}")
                if error_details.get('repository'):
                    print(f"   Repository: {error_details['repository']}")
                if error_details.get('suggestion'):
                    print(f"   Suggestion: {error_details['suggestion']}")
            return
        
        # Display statistics
        stats = results.get("statistics", {})
        print(f"📊 Data Points Statistics:")
        print(f"   Total files: {stats.get('total', 0)}")
        print(f"   Valid files: {stats.get('valid', 0)}")
        print(f"   Invalid files: {stats.get('invalid', 0)}")
        print(f"   Success rate: {stats.get('success_rate', 0.0):.1f}%")
        
        # Display evaluation results
        eval_results = results.get("validation_results", {})
        print(f"\n🎯 Validation Results:")
        print(f"   ✅ Resolved: {eval_results.get('resolved', 0)}")
        print(f"   ❌ Unresolved: {eval_results.get('unresolved', 0)}")
        print(f"   🚨 Errors: {eval_results.get('errors', 0)}")
        
        # Display detailed results if available
        detailed_results = eval_results.get("detailed_results", [])
        if detailed_results:
            print(f"\n📋 Detailed Results:")
            for result in detailed_results:
                instance_id = result.get("instance_id", "unknown")
                status = result.get("status", "unknown")
                status_emoji = "✅" if status == "RESOLVED" else "❌" if status == "UNRESOLVED" else "🚨"
                print(f"   {status_emoji} {instance_id}: {status}")
        
        # Overall success message
        if results.get("success", False):
            print(f"\n🎉 All validations passed successfully!")
        else:
            print(f"\n❌ Validation failed: {results.get('error', 'Unknown error')}")
            if "error_details" in results:
                error_details = results["error_details"]
                print(f"🔍 Error Analysis:")
                print(f"   Type: {error_details.get('type', 'unknown')}")
                print(f"   Message: {error_details.get('message', 'Unknown error')}")
                if error_details.get('repository'):
                    print(f"   Repository: {error_details['repository']}")
                if error_details.get('suggestion'):
                    print(f"   Suggestion: {error_details['suggestion']}")
    
    def get_summary_report(self, results: Dict[str, Any]) -> str:
        """Generate a summary report for GitHub Actions."""
        if not results.get("success", False):
            return f"❌ **Validation Failed**: {results.get('error', 'Unknown error')}"
        
        stats = results.get("statistics", {})
        eval_results = results.get("validation_results", {})
        
        report = f"""## 🔍 SWE-bench Validation Report

**Data Points Processed:** {stats.get('total', 0)}
**Success Rate:** {stats.get('success_rate', 0.0):.1f}%

**Validation Results:**
- ✅ Resolved: {eval_results.get('resolved', 0)}
- ❌ Unresolved: {eval_results.get('unresolved', 0)}
- 🚨 Errors: {eval_results.get('errors', 0)}

"""
        
        if eval_results.get("success", False):
            report += "🎉 **All validations passed successfully!**"
        else:
            report += "⚠️ **Some validations failed. Please check the logs for details.**"
        
        return report
