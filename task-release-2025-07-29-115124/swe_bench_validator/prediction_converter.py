"""
Enhanced converter for transforming data points to SWE-bench prediction format.
"""

import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class PredictionConverter:
    """
    Enhanced converter for transforming SWE-bench data points to prediction format.
    """
    
    def __init__(self, model_name: str = "gold"):
        """
        Initialize the prediction converter.
        
        Args:
            model_name: Name of the model for predictions (default: "gold" for golden patches)
        """
        self.model_name = model_name
        logger.info(f"Initialized PredictionConverter with model: {model_name}")
    
    def convert(self, data_points: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        Convert data points to SWE-bench prediction format.
        
        Args:
            data_points: List of data point dictionaries
            
        Returns:
            List of prediction dictionaries
        """
        logger.info(f"Converting {len(data_points)} data points to predictions format")
        
        predictions = []
        converted_count = 0
        failed_count = 0
        
        for data_point in data_points:
            prediction = self._convert_single(data_point)
            
            if prediction:
                predictions.append(prediction)
                converted_count += 1
                logger.debug(f"Converted data point: {data_point.get('instance_id', 'unknown')}")
            else:
                failed_count += 1
                logger.warning(f"Failed to convert data point: {data_point.get('instance_id', 'unknown')}")
        
        logger.info(f"Conversion completed: {converted_count} successful, {failed_count} failed")
        return predictions
    
    def _convert_single(self, data_point: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Convert a single data point to prediction format.
        
        Args:
            data_point: Data point dictionary
            
        Returns:
            Prediction dictionary or None if conversion failed
        """
        try:
            instance_id = data_point.get("instance_id")
            patch = data_point.get("patch")
            
            if not instance_id or not patch:
                logger.warning(f"Missing required fields in data point: instance_id={instance_id}, patch={'present' if patch else 'missing'}")
                return None
            
            # Validate instance_id
            if not isinstance(instance_id, str) or not instance_id.strip():
                logger.warning(f"Invalid instance_id: {instance_id}")
                return None
            
            # Validate patch
            if not isinstance(patch, str) or not patch.strip():
                logger.warning(f"Invalid patch: empty or not string")
                return None
            
            prediction = {
                "instance_id": instance_id,
                "model_name_or_path": self.model_name,
                "model_patch": patch
            }
            
            logger.debug(f"Successfully converted data point {instance_id}")
            return prediction
            
        except Exception as e:
            logger.error(f"Error converting data point {data_point.get('instance_id', 'unknown')}: {e}")
            return None
    
    def save_to_file(self, predictions: List[Dict[str, str]], file_path: str) -> bool:
        """
        Save predictions to a JSONL file.
        
        Args:
            predictions: List of prediction dictionaries
            file_path: Path to output file
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Saving {len(predictions)} predictions to file: {file_path}")
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                for prediction in predictions:
                    f.write(json.dumps(prediction) + '\n')
            
            logger.info(f"Successfully saved predictions to: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save predictions to {file_path}: {e}")
            return False
    
    def create_dataset_file(self, data_points: List[Dict[str, Any]], file_path: str) -> bool:
        """
        Create dataset file from data points for SWE-bench evaluation.
        
        Args:
            data_points: List of data point dictionaries
            file_path: Path to output dataset file
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Creating dataset file with {len(data_points)} data points: {file_path}")
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                for data_point in data_points:
                    f.write(json.dumps(data_point) + '\n')
            
            logger.info(f"Successfully created dataset file: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create dataset file {file_path}: {e}")
            return False
    
    def get_conversion_summary(self, predictions: List[Dict[str, str]], data_points: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get conversion summary statistics.
        
        Args:
            predictions: List of converted predictions
            data_points: Original data points
            
        Returns:
            Summary statistics
        """
        total_input = len(data_points)
        total_output = len(predictions)
        success_rate = (total_output / total_input) * 100 if total_input > 0 else 0.0
        
        return {
            "total_input": total_input,
            "total_output": total_output,
            "success_rate": success_rate,
            "failed_count": total_input - total_output
        }
