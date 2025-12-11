import os
import json
import shutil

from typing import Any
from typing import Optional

class InternalStorageDataNotFoundError(Exception):
    """Raised when requested data is not found in internal storage."""
    pass

class InternalStorageFileNotFoundError(Exception):
    """Raised when requested file is not found in internal storage."""
    pass

class InternalStorage:
    DATA_FILE_NAME = "data.json"
    
    def __init__(self, root_dir: str):
        self.root_dir = root_dir

    def get_root_dir(self, processor_name: str, algo_version: str, params_version: str) -> str:
        pointer = {
            'processor_name': processor_name,
            'algo_version': algo_version,
            'params_version': params_version
        }
        return os.path.abspath(self._get_dir_path(pointer))

    def set_data(self, processor_name: str, algo_version: str, params_version: str, data: Any) -> dict:
        """Saves the provided data to the internal storage overwriting any existing data associated with the specified `algo_version`, `processor_name` and `params_version`"""
        pointer = {
            'processor_name': processor_name,
            'algo_version': algo_version,
            'params_version': params_version
        }
        
        # Create directories if they don't exist
        dir_path = self._get_dir_path(pointer)
        os.makedirs(dir_path, exist_ok=True)
        
        # Write data to data.json file
        data_file_path = self._get_data_file_path(pointer)
        with open(data_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        return data_file_path

    def get_data(self, processor_name: str, algo_version: str, params_version: str, default_value: Any = None) -> dict:
        """Retrieves data associated with the provided `algo_version`, `processor_name` and `params_version` from the internal storage."""
        """Throws an exception if no data is associated with the provided `algo_version`, `processor_name` and `params_version`."""
        pointer = {
            'processor_name': processor_name,
            'algo_version': algo_version,
            'params_version': params_version
        }
        
        if not self.has_data(processor_name, algo_version, params_version):
            if default_value != None: return default_value
            data_file_path = self._get_data_file_path(pointer)
            raise InternalStorageDataNotFoundError(f"No data found for processor_name='{processor_name}', algo_version={algo_version}, params_version='{params_version}' at path: {data_file_path}")
        
        data_file_path = self._get_data_file_path(pointer)
        with open(data_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def has_data(self, processor_name: str, algo_version: str, params_version: str) -> bool:
        """Tests the internal storage for existance of the data associated with the specified `algo_version`, `processor_name` and `params_version`."""
        pointer = {
            'processor_name': processor_name,
            'algo_version': algo_version,
            'params_version': params_version
        }
        
        data_file_path = self._get_data_file_path(pointer)
        return os.path.exists(data_file_path)

    def remove_data(self, processor_name: Optional[str] = None, algo_version: Optional[int] = None, params_version: Optional[str] = None) -> list[dict]:
        """Removes data from the internal storage based on the specified filters.
    
        If all parameters are None, removes all data. Specifying values for one or more 
        parameters narrows the removal to only data matching those criteria.
    
        Args:
            processor_name: If specified, only removes data with this processor name  
            algo_version: If specified, only removes data with this algo version
            params_version: If specified, only removes data with this params version
        """
        filter_pointer = {
            'processor_name': processor_name,
            'algo_version': algo_version,
            'params_version': params_version
        }
        
        # Scan for matching data files
        matching_pointers = self._scan_data_pointers(filter_pointer)

        result = []

        # Remove each data file
        for pointer in matching_pointers:
            data_file_path = self._get_data_file_path(pointer)
            os.remove(data_file_path)
            result.append(data_file_path)

        return result

    def add_file(self, processor_name: str, algo_version: str, params_version: str, is_file_name: str, is_src_dir: str) -> dict:
        """Copies the specified file to the internal storage overwriting an existing file if present having the same file name and associated with the specified `algo_version`, `processor_name` and `params_version`"""
        pointer = {
            'processor_name': processor_name,
            'algo_version': algo_version,
            'params_version': params_version,
            'is_file_name': is_file_name
        }
        
        # Create directories if they don't exist
        dir_path = self._get_dir_path(pointer)
        os.makedirs(dir_path, exist_ok=True)
        
        # Copy file from source directory to destination
        src_file_path = os.path.join(is_src_dir, is_file_name)
        dest_file_path = self._get_file_path(pointer)
        shutil.copy2(src_file_path, dest_file_path)

        return dest_file_path

    def add_move_file(self, processor_name: str, algo_version: str, params_version: str, is_file_name: str, is_src_dir: str) -> dict:
        """Moves the specified file to the internal storage overwriting an existing file if present having the same file name and associated with the specified `algo_version`, `processor_name` and `params_version`"""
        pointer = {
            'processor_name': processor_name,
            'algo_version': algo_version,
            'params_version': params_version,
            'is_file_name': is_file_name
        }
        
        # Create directories if they don't exist
        dir_path = self._get_dir_path(pointer)
        os.makedirs(dir_path, exist_ok=True)
        
        # Copy file from source directory to destination
        src_file_path = os.path.join(is_src_dir, is_file_name)
        dest_file_path = self._get_file_path(pointer)
        shutil.move(src_file_path, dest_file_path)

        return dest_file_path

    def get_file(self, processor_name: str, algo_version: str, params_version: str, is_file_name: str) -> str:
        """Retrieves a the file full path of a file having the same file name and associated with the specified `algo_version`, `processor_name` and `params_version` from the internal storage"""
        """Throws an exception if no such file exists."""
        pointer = {
            'processor_name': processor_name,
            'algo_version': algo_version,
            'params_version': params_version,
            'is_file_name': is_file_name
        }
        
        inst_file_path = self._get_file_path(pointer)
        if not os.path.exists(inst_file_path):
            raise FileNotFoundError(f"No file '{is_file_name}' found for processor_name='{processor_name}', algo_version={algo_version}, params_version='{params_version}' at path: {inst_file_path}")
        
        return inst_file_path

    def has_file(self, processor_name: str, algo_version: str, params_version: str, is_file_name: str) -> bool:
        """Tests the internal storage for existance of the file having the same file name and associated with the specified `algo_version`, `processor_name` and `params_version`."""
        pointer = {
            'processor_name': processor_name,
            'algo_version': algo_version,
            'params_version': params_version,
            'is_file_name': is_file_name
        }
        
        inst_file_path = self._get_file_path(pointer)
        return os.path.exists(inst_file_path)

    def remove_files(self, processor_name: Optional[str] = None, algo_version: Optional[int] = None, params_version: Optional[str] = None, is_file_name: Optional[str] = None) -> list[dict]:
        """Removes files from the internal storage based on the specified filters.
    
        If all parameters are None, removes all files. Specifying values for one or more 
        parameters narrows the removal to only files matching those criteria.
    
        Args:
            processor_name: If specified, only removes files with this processor name  
            algo_version: If specified, only removes files with this algo version
            params_version: If specified, only removes files with this params version
            is_file_name: If specified, only removes files with this name
        """
        filter_pointer = {
            'processor_name': processor_name,
            'algo_version': algo_version,
            'params_version': params_version,
            'is_file_name': is_file_name
        }
        
        # Scan for matching files
        matching_pointers = self._scan_file_pointers(filter_pointer)
        
        result = []

        # Remove each file
        for pointer in matching_pointers:
            inst_file_path = self._get_file_path(pointer)
            os.remove(inst_file_path)
            result.append(inst_file_path)

        return result

    def remove(self, processor_name: Optional[str] = None, algo_version: Optional[int] = None, params_version: Optional[str] = None) -> list[dict]:
        """Removes data files from the internal storage based on the specified filters.

        If all parameters are None, removes all files. Specifying values for one or more 
        parameters narrows the removal to only files matching those criteria.

        Args:
            processor_name: If specified, only removes files with this processor name  
            algo_version: If specified, only removes files with this algo version
            params_version: If specified, only removes files with this params version
        """
    
        result = (self.remove_data(processor_name, algo_version, params_version) + 
                  self.remove_files(processor_name, algo_version, params_version))
    
        # Remove empty directories
        self._remove_empty_directories()
    
        return result


    def _remove_empty_directories(self):
        """Remove all empty directories under root_dir, repeat until no empty directories are left."""
        if not os.path.exists(self.root_dir):
            return
    
        while True:
            empty_dirs_removed = False
        
            # Walk through all directories (bottom-up to handle nested empty dirs)
            for root, dirs, files in os.walk(self.root_dir, topdown=False):
                # Skip the root directory itself
                if root == self.root_dir:
                    continue
                
                # Check if directory is empty (no files and no subdirectories)
                if not files and not dirs:
                    try:
                        os.rmdir(root)
                        empty_dirs_removed = True
                    except FileNotFoundError:
                        pass
        
            # If no empty directories were removed, we're done
            if not empty_dirs_removed:
                break

    def _get_dir_path(self, pointer: dict) -> str:
        """Returns the directory path for the given pointer."""
        return os.path.join(
            self.root_dir,
            pointer['processor_name'],
            pointer['algo_version'],
            pointer['params_version']
        )

    def _get_data_file_path(self, pointer: dict) -> str:
        """Returns the data.json file path for the given pointer."""
        dir_path = self._get_dir_path(pointer)
        return os.path.join(dir_path, self.DATA_FILE_NAME)

    def _get_file_path(self, pointer: dict) -> str:
        """Returns the file path for the given pointer (requires is_file_name in pointer)."""
        dir_path = self._get_dir_path(pointer)
        return os.path.join(dir_path, pointer['is_file_name'])

    def _scan_data_pointers(self, filter_pointer: dict) -> list[dict]:
        """Returns a list of pointers for data.json files that match the filter criteria."""
        # Step 1: Get all files under root_dir
        all_files = self._get_all_files()
    
        # Step 2: Filter files based on query parameters (None = wildcard)
        result = []
        for file_parts in all_files:
            processor_name, algo_version, params_version, filename = file_parts
        
            # Must be data.json file
            if filename != self.DATA_FILE_NAME:
                continue
            
            # Check if matches filter criteria (None means match any)
            if (filter_pointer['processor_name'] is None or filter_pointer['processor_name'] == processor_name) and \
               (filter_pointer['algo_version'] is None or filter_pointer['algo_version'] == algo_version) and \
               (filter_pointer['params_version'] is None or filter_pointer['params_version'] == params_version):
            
                pointer = {
                    'processor_name': processor_name,
                    'algo_version': algo_version,
                    'params_version': params_version
                }
                result.append(pointer)
    
        return result

    def _scan_file_pointers(self, filter_pointer: dict) -> list[dict]:
        """Returns a list of pointers for files (excluding data.json) that match the filter criteria."""
        # Step 1: Get all files under root_dir
        all_files = self._get_all_files()
    
        # Step 2: Filter files based on query parameters (None = wildcard)
        result = []
        for file_parts in all_files:
            processor_name, algo_version, params_version, filename = file_parts
        
            # Must NOT be data.json file
            if filename == self.DATA_FILE_NAME:
                continue
            
            # Check if matches filter criteria (None means match any)
            if (filter_pointer['processor_name'] is None or filter_pointer['processor_name'] == processor_name) and \
               (filter_pointer['algo_version'] is None or filter_pointer['algo_version'] == algo_version) and \
               (filter_pointer['params_version'] is None or filter_pointer['params_version'] == params_version) and \
               (filter_pointer['is_file_name'] is None or filter_pointer['is_file_name'] == filename):
            
                pointer = {
                    'processor_name': processor_name,
                    'algo_version': algo_version,
                    'params_version': params_version,
                    'is_file_name': filename
                }
                result.append(pointer)
    
        return result

    def _get_all_files(self) -> list[list[str]]:
        """Get all files under root_dir in format ["processor_name", "algo_version", "params_version", "filename"]"""
        all_files = []
        if not os.path.exists(self.root_dir):
            return all_files
    
        for root, dirs, files in os.walk(self.root_dir):
            for filename in files:
                # Get relative path from root_dir
                rel_path = os.path.relpath(root, self.root_dir)
                path_parts = rel_path.split(os.sep)
            
                # Add filename to path parts
                path_parts.append(filename)
                all_files.append(path_parts)
    
        return all_files