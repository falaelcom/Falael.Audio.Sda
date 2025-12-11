import threading
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Callable, List, Any, Optional

def _process_single_item_wrapper(args):
    """Wrapper function to handle item processing for multiprocessing"""
    item_index, item, processor_fn, context_obj = args
    return processor_fn(item_index, item, context_obj)

def parallel_forEach_collection(
    collection: List[Any],
    processor_fn: Callable[[int, Any, Any], Any],
    context_obj: Any,
    max_workers: Optional[int] = None,
    use_processes: bool = True,
    enable_parallel: bool = True
) -> List[Any]:
    """
    Process a collection of items in parallel while preserving order.
    
    Args:
        collection: List of items to process (can be any type)
        processor_fn: Function to process each item
                     Signature: (item_index: int, item: Any, context: Any) -> Any
        context_obj: Untyped context object passed to processor function
        max_workers: Maximum number of workers (None = auto-detect)
        use_processes: If True, use ProcessPoolExecutor for CPU-bound tasks.
                      If False, use ThreadPoolExecutor for I/O-bound or quick tasks.
        enable_parallel: If True, process in parallel; if False, process sequentially.
    
    Returns:
        List of results in original collection order
    """
    
    if not collection:
        return []
    
    if not enable_parallel:
        # Sequential processing
        results = []
        for i, item in enumerate(collection):
            result = processor_fn(i, item, context_obj)
            results.append(result)
        return results
    
    if use_processes:
        # Use ProcessPoolExecutor for CPU-intensive tasks
        # Prepare arguments for each item
        item_args = []
        for i, item in enumerate(collection):
            item_args.append((i, item, processor_fn, context_obj))
        
        # Process all items in parallel
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Submit all item processing tasks
            futures = []
            for args in item_args:
                future = executor.submit(_process_single_item_wrapper, args)
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
        results = [None] * len(collection)
        lock = threading.Lock()
        
        def process_single_item_thread(item_index: int) -> None:
            """Process a single item and store result at correct index"""
            item = collection[item_index]
            
            # Call the processor function - let exceptions bubble up
            result = processor_fn(item_index, item, context_obj)
            
            # Thread-safe result storage
            with lock:
                results[item_index] = result
        
        # Process all items in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all item processing tasks
            futures = []
            for i in range(len(collection)):
                future = executor.submit(process_single_item_thread, i)
                futures.append(future)
            
            # Wait for all tasks to complete
            for future in futures:
                future.result()  # This will raise any exceptions that occurred
        
        return results