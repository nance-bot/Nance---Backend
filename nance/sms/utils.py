import requests

def call_ml_model_util(narration: str, source_type: str = "SMS") -> dict:
    """Placeholder ML model utility - replace with your actual ML service URL."""
    if not narration:
        raise ValueError("Narration is required.")

    try:
        # Replace this URL with your actual ML service endpoint
        res = requests.post(
            "https://your-ml-service.com/process-content",  # Replace with actual URL
            json={"content": narration, "type": source_type},
            timeout=15
        )
        res.raise_for_status()
        return res.json()
    except requests.RequestException as e:
        raise RuntimeError(f"ML service call failed: {str(e)}")