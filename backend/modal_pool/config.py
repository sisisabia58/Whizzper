import os
from typing import List, Dict, Any

def get_pool_config() -> Dict[str, Any]:
    endpoints_str = os.environ.get("MODAL_ENDPOINTS", "")
    endpoints: List[str] = []
    
    seen = set()
    
    # Process MODAL_ENDPOINTS
    if endpoints_str:
        for ep in endpoints_str.split(","):
            ep_clean = ep.strip()
            if ep_clean and ep_clean not in seen:
                endpoints.append(ep_clean)
                seen.add(ep_clean)
    else:
        # Process MODAL_WEB_ENDPOINT_URL as fallback
        fallback = os.environ.get("MODAL_WEB_ENDPOINT_URL", "").strip()
        if fallback:
            for ep in fallback.split(","):
                ep_clean = ep.strip()
                if ep_clean and ep_clean not in seen:
                    endpoints.append(ep_clean)
                    seen.add(ep_clean)
            
    if not endpoints:
        raise ValueError("No Modal endpoints configured. Please set MODAL_ENDPOINTS or MODAL_WEB_ENDPOINT_URL.")

    per_endpoint_cap = int(os.environ.get("POOL_PER_ENDPOINT_CAP", "10"))
    unhealthy_threshold = int(os.environ.get("POOL_UNHEALTHY_THRESHOLD", "3"))
    cooldown_seconds = int(os.environ.get("POOL_COOLDOWN_SECONDS", "60"))
    max_retries = int(os.environ.get("POOL_MAX_RETRIES", "2"))

    return {
        "endpoints": endpoints,
        "per_endpoint_cap": per_endpoint_cap,
        "unhealthy_threshold": unhealthy_threshold,
        "cooldown_seconds": cooldown_seconds,
        "max_retries": max_retries,
    }
