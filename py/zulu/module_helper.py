import os
import importlib
import glob
import re
import sys

def preimport_modules(directory_path, accept_patterns, recursive=True):
    """
    Import all Python modules from the specified directory using proper package imports.
    This will populate namespace packages with all their submodules.
    
    Args:
        directory_path (str): Path to the directory containing Python modules
        accept_patterns (list): List of regex patterns to filter modules to load.
                               Only modules matching at least one pattern will be imported.
                               If empty list, no modules will be imported.
        recursive (bool): If True, recursively import from subdirectories
    """
    if not os.path.isdir(directory_path):
        raise ValueError(f"Directory does not exist: {directory_path}")
    
    # Normalize the directory path
    directory_path = os.path.normpath(directory_path)
    
    # If accept_patterns is empty, do nothing
    if not accept_patterns:
        return
    
    # Compile regex patterns for efficiency
    compiled_patterns = [re.compile(pattern) for pattern in accept_patterns]
    
    # Use glob to find all Python files
    if recursive:
        pattern = os.path.join(directory_path, "**", "*.py")
        py_files = glob.glob(pattern, recursive=True)
    else:
        pattern = os.path.join(directory_path, "*.py")
        py_files = glob.glob(pattern)
    
    for py_file in py_files:
        # Skip __init__.py and other dunder files
        if os.path.basename(py_file).startswith('__'):
            continue
        
        # Get relative path from the base directory
        try:
            relative_path = os.path.relpath(py_file, directory_path)
        except ValueError:
            # Skip files that can't be made relative (different drives on Windows)
            continue
            
        # Convert file path to module name
        module_path = relative_path[:-3].replace(os.sep, ".")
        
        # Skip if it starts with a dot (hidden files/dirs)
        if module_path.startswith('.'):
            continue
        
        # Apply accept patterns filter
        if not any(pattern.search(module_path) for pattern in compiled_patterns):
            continue
        
        importlib.import_module(module_path)

def import_module_dynamically(module_name):
    """
    Dynamically import a module by name from any currently imported package.
    
    Args:
        module_name (str): Name of the module to import (e.g., 'ch_left_extract_fulltrack')
    
    Returns:
        module: The imported module object
    
    Raises:
        ImportError: If the module is not found in any imported package
    """
    for package_name, package in sys.modules.items():
        if hasattr(package, module_name):
            try:
                return importlib.import_module(f"{package_name}.{module_name}")
            except ImportError:
                continue
    raise ImportError(f"Module {module_name} not found in any imported package")