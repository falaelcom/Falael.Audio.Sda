import os
import json

from pathlib import Path
from typing import Tuple

import hashlib

def get_keys(key: dict) -> Tuple[dict, str]: 
    return (key, get_key_hash(key))

def get_key_json(key: dict):
    json_str = json.dumps(key, sort_keys=True, separators=(',', ':'))
    return json_str

def get_key_hash(key: dict):
    json_str = json.dumps(key, sort_keys=True, separators=(',', ':'))
    # return hashlib.sha256(json_str.encode('utf-8')).hexdigest() # 64 chars is too long for a cache directory name
    return hashlib.sha1(json_str.encode('utf-8')).hexdigest() # using sha1 with 40 chars

def get_file_timestamp(fscu_file_path: str):
    """
    Get file creation timestamp.
    
    Args:
        fscu_file_path (str or Path): Path to the file
        
    Returns:
        float: File creation timestamp
        
    Raises:
        OSError: If file doesn't exist or can't be accessed
    """
    fscu_file_path = Path(fscu_file_path)
    if not fscu_file_path.exists():
        return -1.0
    
    return os.path.getmtime(fscu_file_path)

def get_file_timestamps(root_dir, file_paths):
    result = {}
    
    for fscu_file_path in file_paths:
        result[fscu_file_path] = get_file_timestamp(os.path.join(root_dir, fscu_file_path) )
    
    return result

def sanitate_params(data: dict, once: list = None, remove: list = None, seen_once_keys: set = None) -> dict:
    """
    Removes keys from dictionary based on the 'once' and 'remove' lists.
    Recursive function that handles up to 3 levels deep.
    
    Args:
        data: Dictionary to filter
        once: List of key names to remove only on second occurrence
        remove: List of key names to always remove
        seen_once_keys: Internal parameter to track seen keys across recursion
        
    Returns:
        Filtered dictionary
    """
    # Initialize parameters and seen set at top level
    if once is None:
        once = []
    if remove is None:
        remove = []
    if seen_once_keys is None:
        seen_once_keys = set()
    
    result = {}
    
    for key, value in data.items():
        # Always remove keys from 'remove' list
        if key in remove:
            continue
        
        # Handle 'once' keys - remove only on second occurrence
        if key in once:
            if key in seen_once_keys:
                continue  # Second occurrence, remove it
            else:
                seen_once_keys.add(key)  # First occurrence, keep it
        
        # If value is a dict, recursively process it
        if isinstance(value, dict):
            filtered_value = sanitate_params(value, once, remove, seen_once_keys)
            result[key] = filtered_value
        else:
            result[key] = value
    
    return result