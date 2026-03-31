import os
import joblib
from datetime import datetime, UTC
from typing import Dict, Any, Optional

class ModelRegistry:
    """
    Handles model saving, versioning, and retrieval from the filesystem/S3.
    """
    BASE_PATH = "app/ml/store"
    
    @staticmethod
    def save_model(model: Any, name: str, metrics: Dict[str, float]) -> str:
        version = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        model_dir = os.path.join(ModelRegistry.BASE_PATH, name, version)
        os.makedirs(model_dir, exist_ok=True)
        
        # Save model artifact
        path = os.path.join(model_dir, "model.joblib")
        joblib.dump(model, path)
        
        # Save metadata/metrics
        with open(os.path.join(model_dir, "metadata.json"), "w") as f:
            import json
            json.dump({
                "name": name,
                "version": version,
                "metrics": metrics,
                "timestamp": datetime.now(UTC).isoformat()
            }, f)
            
        # Update 'latest' pointer (symlink or file)
        latest_link = os.path.join(ModelRegistry.BASE_PATH, name, "latest_version")
        with open(latest_link, "w") as f:
            f.write(version)
            
        return version

    @staticmethod
    def load_latest_model(name: str) -> Optional[Any]:
        try:
            latest_link = os.path.join(ModelRegistry.BASE_PATH, name, "latest_version")
            if not os.path.exists(latest_link):
                return None
                
            with open(latest_link, "r") as f:
                version = f.read().strip()
                
            path = os.path.join(ModelRegistry.BASE_PATH, name, version, "model.joblib")
            return joblib.load(path)
        except Exception as e:
            print(f"Error loading model {name}: {e}")
            return None
