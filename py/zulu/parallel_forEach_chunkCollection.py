import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, List, Dict, Any, Optional

import os
import threading
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Callable, List, Dict, Any, Optional

def _process_single_chunk_wrapper(args):
    """Wrapper function to handle chunk processing for multiprocessing"""
    chunk_index, chunk_filename, out_path, callback_fn, context_obj = args
    chunk_path = os.path.join(out_path, chunk_filename)
    return callback_fn(chunk_index, chunk_filename, chunk_path, context_obj)

def parallel_forEach_chunkCollection(
    callback_fn: Callable[[int, str, str, Any], Any],
    chunk_list: List[str],
    out_path: str,
    context_obj: Any,
    max_workers: Optional[int] = None,
    use_processes: bool = True
) -> List[Any]:
    """
    Process chunks in parallel with a simple callback approach.
    
    Args:
        callback_fn: Function to process each chunk
                    Signature: (chunk_index: int, chunk_filename: str, chunk_path: str, context: Any) -> Any
        chunk_list: List of chunk filenames (relative to out_path)
        out_path: Base output directory path where chunks are located
        context_obj: Untyped context object passed to callback
        max_workers: Maximum number of workers (None = auto-detect)
        use_processes: If True, use ProcessPoolExecutor for CPU-bound tasks.
                      If False, use ThreadPoolExecutor for I/O-bound or quick tasks.
    
    Returns:
        List of results in original chunk order
    """
    
    if not chunk_list:
        return []
    
    if use_processes:
        # Use ProcessPoolExecutor for CPU-intensive tasks
        # Prepare arguments for each chunk
        chunk_args = []
        for i, chunk_filename in enumerate(chunk_list):
            chunk_args.append((i, chunk_filename, out_path, callback_fn, context_obj))
        
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Submit all chunk processing tasks
            futures = []
            for args in chunk_args:
                future = executor.submit(_process_single_chunk_wrapper, args)
                futures.append(future)
            
            # Collect results in order
            results = []
            for future in futures:
                result = future.result()  # This will raise any exceptions that occurred
                results.append(result)
        
        return results
    
    else:
        # Use ThreadPoolExecutor for I/O-bound or quick tasks
        # Pre-allocate results array to preserve order
        results = [None] * len(chunk_list)
        lock = threading.Lock()
        
        def process_single_chunk_thread(chunk_index: int) -> None:
            """Process a single chunk and store result at correct index"""
            chunk_filename = chunk_list[chunk_index]
            chunk_path = os.path.join(out_path, chunk_filename)
            
            # Call the callback function - let exceptions bubble up
            result = callback_fn(chunk_index, chunk_filename, chunk_path, context_obj)
            
            # Thread-safe result storage
            with lock:
                results[chunk_index] = result
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all chunk processing tasks
            futures = []
            for i in range(len(chunk_list)):
                future = executor.submit(process_single_chunk_thread, i)
                futures.append(future)
            
            # Wait for all tasks to complete
            for future in futures:
                future.result()  # This will raise any exceptions that occurred
        
        return results