"""
Enhanced data loader for SWE-bench data points with comprehensive validation.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class DataPointReader:
    """
    Enhanced reader for SWE-bench data points from JSON files with comprehensive validation.
    """
    
    def __init__(self):
        """Initialize the data point reader."""
        self.required_fields = [
            "instance_id",
            "repo", 
            "base_commit",
            "patch",
            "FAIL_TO_PASS",
            "PASS_TO_PASS"
        ]
        
        self.optional_fields = [
            "problem_statement",
            "hints_text",
            "created_at",
            "version",
            "environment_setup_commit",
            "_download_metadata"
        ]
    
    def load(self, data_dir: Path, files: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Load data points from JSON files with enhanced validation.
        
        Args:
            data_dir: Directory containing data point JSON files
            files: Optional list of specific file names to load (without .json extension)
            
        Returns:
            List of validated data point dictionaries
        """
        logger.info(f"Loading data points from directory: {data_dir}")
        
        if not data_dir.exists():
            logger.error(f"Data points directory does not exist: {data_dir}")
            return []
        
        data_points = []
        
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
                else:
                    logger.warning(f"Specified file not found: {file}")
        
        logger.info(f"Processing {len(json_files)} JSON files")
        
        if not json_files:
            logger.warning("No JSON files found to process")
            return []
        
        for json_file in json_files:
            logger.info(f"Loading data point from file: {json_file.name}")
            data_point = self._load_single(json_file)
            
            if data_point:
                instance_id = data_point.get("instance_id", "unknown")
                logger.info(f"Loaded data point: {instance_id}")
                data_points.append(data_point)
            else:
                logger.warning(f"Failed to load data point from file: {json_file.name}")
        
        logger.info(f"Total data points loaded: {len(data_points)}")
        return data_points
    
    def _load_single(self, json_file: Path) -> Optional[Dict[str, Any]]:
        """
        Load a single data point from a JSON file with comprehensive validation.
        
        Args:
            json_file: Path to JSON file
            
        Returns:
            Data point dictionary or None if loading failed
        """
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data_point = json.load(f)
            
            validation_result = self._validate_comprehensive(data_point, json_file.name)
            
            if validation_result["valid"]:
                return data_point
            else:
                logger.warning(f"Data point validation failed for {json_file.name}: {validation_result['errors']}")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in {json_file.name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading {json_file.name}: {e}")
            return None
    
    def _validate_comprehensive(self, data_point: Dict[str, Any], filename: str) -> Dict[str, Any]:
        """
        Comprehensive validation of a data point with detailed error reporting.
        
        Args:
            data_point: Data point dictionary
            filename: Name of the file being validated
            
        Returns:
            Validation result with detailed error information
        """
        errors = []
        warnings = []
        
        # Check required fields
        for field in self.required_fields:
            if field not in data_point:
                errors.append(f"Missing required field: '{field}'")
            elif not data_point[field]:
                errors.append(f"Empty required field: '{field}'")
        
        # Validate specific fields
        if "instance_id" in data_point:
            instance_id = data_point["instance_id"]
            if not isinstance(instance_id, str) or not instance_id.strip():
                errors.append("instance_id must be a non-empty string")
        
        if "repo" in data_point:
            repo = data_point["repo"]
            if not isinstance(repo, str) or not repo.strip():
                errors.append("repo must be a non-empty string")
            elif "/" not in repo:
                warnings.append("repo should be in format 'owner/repository'")
        
        if "base_commit" in data_point:
            commit = data_point["base_commit"]
            if not isinstance(commit, str) or len(commit) != 40:
                errors.append("base_commit must be a 40-character SHA hash")
        
        if "patch" in data_point:
            patch = data_point["patch"]
            if not isinstance(patch, str) or not patch.strip():
                errors.append("patch must be a non-empty string")
            elif not patch.startswith("diff --git"):
                warnings.append("patch should start with 'diff --git'")
        
        # Validate test arrays
        if "FAIL_TO_PASS" in data_point:
            fail_to_pass = data_point["FAIL_TO_PASS"]
            if isinstance(fail_to_pass, str):
                try:
                    fail_to_pass = json.loads(fail_to_pass)
                except json.JSONDecodeError:
                    errors.append("FAIL_TO_PASS must be valid JSON array")
            elif not isinstance(fail_to_pass, list):
                errors.append("FAIL_TO_PASS must be a list")
        
        if "PASS_TO_PASS" in data_point:
            pass_to_pass = data_point["PASS_TO_PASS"]
            if isinstance(pass_to_pass, str):
                try:
                    pass_to_pass = json.loads(pass_to_pass)
                except json.JSONDecodeError:
                    errors.append("PASS_TO_PASS must be valid JSON array")
            elif not isinstance(pass_to_pass, list):
                errors.append("PASS_TO_PASS must be a list")
        
        # Check if at least one test array has content
        fail_to_pass = data_point.get("FAIL_TO_PASS", [])
        pass_to_pass = data_point.get("PASS_TO_PASS", [])
        
        if isinstance(fail_to_pass, str):
            try:
                fail_to_pass = json.loads(fail_to_pass)
            except:
                fail_to_pass = []
        
        if isinstance(pass_to_pass, str):
            try:
                pass_to_pass = json.loads(pass_to_pass)
            except:
                pass_to_pass = []
        
        if not fail_to_pass and not pass_to_pass:
            errors.append("At least one of FAIL_TO_PASS or PASS_TO_PASS must contain tests")
        
        # Check optional fields
        for field in self.optional_fields:
            if field in data_point and not data_point[field]:
                warnings.append(f"Optional field '{field}' is empty")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "filename": filename
        }
    
    def get_validation_summary(self, data_points: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get validation summary for loaded data points.
        
        Args:
            data_points: List of loaded data points
            
        Returns:
            Summary statistics
        """
        total = len(data_points)
        
        if total == 0:
            return {
                "total": 0,
                "valid": 0,
                "invalid": 0,
                "success_rate": 0.0
            }
        
        # Count valid data points (those that passed validation)
        valid_count = total  # All loaded data points are valid
        
        return {
            "total": total,
            "valid": valid_count,
            "invalid": 0,
            "success_rate": (valid_count / total) * 100 if total > 0 else 0.0
        }
