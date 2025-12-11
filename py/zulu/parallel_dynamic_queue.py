import threading
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from collections import deque
from typing import Callable, List, Any, Optional
import time

def parallel_dynamic_queue(
    collection: deque,
    processor_fn: Callable[[int, Any, Any], Any],
    completion_callback: Callable[[Any, Any, dict], None],
    context_obj: Any,
    max_workers: Optional[int] = None,
    use_processes: bool = True
) -> List[Any]:
    """
    Process a dynamic queue where processor functions can return items to re-enqueue.
    
    Processing continues until the queue is empty AND no processor functions are running.
    The processor function can return None (completed) or an object to re-enqueue.
    
    Args:
        collection: Initial queue (deque) of items to process
        processor_fn: Function to process each item
                     Signature: (item_index: int, item: Any, context: Any) -> Any
                     Returns: None for completed items, or object to re-enqueue
        completion_callback: Function called when an item completes processing (returns None)
                           Signature: (item: Any, result: None, stats: dict) -> None
        context_obj: Context object passed to processor function
        max_workers: Maximum number of workers (None = auto-detect)
        use_processes: If True, use ProcessPoolExecutor for CPU-bound tasks.
                      If False, use ThreadPoolExecutor for I/O-bound or quick tasks.
    
    Returns:
        List of all results produced by processor functions (in processing order)
    """
    
    if not collection:
        return []
    
    # Thread-safe queue and state management
    processing_queue = deque(collection)  # Copy the input queue
    queue_lock = threading.Lock()
    
    results = []
    item_counter = 0  # For unique item indexing
    completed_count = 0  # Track completed items
    
    # Track timing and chunk processing
    chunk_timings = {}  # chunk_id -> {'start_time': ..., 'total_time_ms': ...}
    task_start_times = {}  # future -> start_time
    
    # Choose executor based on use_processes flag
    ExecutorClass = ProcessPoolExecutor if use_processes else ThreadPoolExecutor
    
    with ExecutorClass(max_workers=max_workers) as executor:
        while True:
            # Collect items to process in this batch
            current_batch = []
            batch_indices = []
            
            with queue_lock:
                # Take up to max_workers items from queue
                batch_size = min(len(processing_queue), max_workers or len(processing_queue))
                for _ in range(batch_size):
                    if processing_queue:
                        item = processing_queue.popleft()
                        current_batch.append(item)
                        batch_indices.append(item_counter)
                        item_counter += 1
            
            if not current_batch:
                # Queue is empty, we're done
                break
            
            # Submit batch for processing
            futures = []
            for i, item in enumerate(current_batch):
                # Use wrapper function for both processes and threads for consistency
                args = (batch_indices[i], item, context_obj)
                future = executor.submit(_process_queue_item_wrapper, args, processor_fn)
                futures.append(future)
                
                # Track start time for this task
                task_start_times[future] = time.time()
                
                # Initialize chunk timing if this is a new chunk
                chunk_id = _get_chunk_id(item)
                if chunk_id not in chunk_timings:
                    chunk_timings[chunk_id] = {
                        'first_start_time': time.time(),
                        'total_time_ms': 0.0
                    }
            
            # Collect results and handle re-enqueuing
            for i, future in enumerate(futures):
                item = current_batch[i]
                start_time = task_start_times[future]
                
                try:
                    result = future.result()  # This will raise any exceptions
                    end_time = time.time()
                    processing_time_ms = (end_time - start_time) * 1000
                    
                    # Update chunk timing
                    chunk_id = _get_chunk_id(item)
                    chunk_timings[chunk_id]['total_time_ms'] += processing_time_ms
                    
                    if result is not None:
                        # This is an item to re-enqueue
                        with queue_lock:
                            processing_queue.append(result)
                    else:
                        # None result means completed
                        completed_count += 1
                        stats = {
                            'total_completed': completed_count,
                            'remaining_iterations': len(processing_queue),
                            'queue_size': len(processing_queue),
                            'processing_time_ms': processing_time_ms,
                            'total_processing_time_ms': chunk_timings[chunk_id]['total_time_ms'],
                            'queue_wait_time_ms': 0
                        }
                        completion_callback(item, None, stats)
                        
                except Exception:
                    # Re-raise the exception
                    raise
                finally:
                    # Clean up timing tracking
                    if future in task_start_times:
                        del task_start_times[future]
    
    return results

def _get_chunk_id(item: Any) -> str:
    """
    Extract a unique identifier for chunk timing tracking.
    Handles both dict objects and other item types.
    """
    if isinstance(item, dict):
        # For chunk objects, use chunk_index as identifier
        return str(item.get('chunk_index', id(item)))
    else:
        # For other items, use object id
        return str(id(item))

def _process_queue_item_wrapper(args, processor_fn):
    """Wrapper function to handle queue item processing for multiprocessing"""
    item_index, item, context_obj = args
    return processor_fn(item_index, item, context_obj)