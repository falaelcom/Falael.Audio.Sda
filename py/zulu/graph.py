from zulu.Symbol import Symbol

# Symbol values for vertex cardinalities
Cardinality_Zero = Symbol("Cardinality_Zero")       # Atomic vertices
Cardinality_AlephNull = Symbol("Cardinality_AlephNull")  # Countable composites (lists)
Cardinality_AlephOne = Symbol("Cardinality_AlephOne")   # Uncountable composites (dicts)
Cardinality_Void = Symbol("Cardinality_Void")       # Void (non-existent) vertices

# Merge policy sentinel values
Merge_Fail = Symbol("Merge_Fail")
Merge_Keep = Symbol("Merge_Keep")
Merge_Overwrite = Symbol("Merge_Overwrite")

# Dict key order sentinel values
DictKeyOrder_FirstWins = Symbol("DictKeyOrder_FirstWins")
DictKeyOrder_LastWins = Symbol("DictKeyOrder_LastWins")

class JsonFabric:
    """
    Fabric implementation for JSON-like structures following TP v1.0 specifications.
    Recognizes dicts as uncountable composites, lists as countable composites, 
    and all other values as atomic vertices.
    """
    
    def get_vertex_cardinality(self, vertex):
        """
        Recognize vertex cardinality based on vertex type.
        Returns: Cardinality_Zero, Cardinality_AlephNull, or Cardinality_AlephOne
        """
        if isinstance(vertex, dict): return Cardinality_AlephOne   # Uncountable composite
        elif isinstance(vertex, list): return Cardinality_AlephNull  # Countable composite
        else: return Cardinality_Zero       # Atomic vertex
    
    def get_label_cardinality(self, label):
        """
        Recognize label cardinality based on label type.
        Returns: Cardinality_AlephNull for integers, Cardinality_AlephOne for strings
        """
        if isinstance(label, int): return Cardinality_AlephNull  # Countable label
        else: return Cardinality_AlephOne   # Uncountable label (string)
    
    def arc_exists(self, tail_vertex, label):
        """
        Check if an arc with the given label exists starting from tail_vertex.
        Returns: True if arc exists, False otherwise
        """
        if isinstance(tail_vertex, dict): return label in tail_vertex
        elif isinstance(tail_vertex, list): return isinstance(label, int) and 0 <= label < len(tail_vertex)
        else: return False  # Atomic vertices have no arcs
    
    def create_countable_composite(self, initial_size=None):
        """
        Create a new countable composite vertex (list).
        Args:
            initial_size: Optional initial size for the list
        Returns: New empty list or list with specified size
        """
        if initial_size is None: return []
        else: return [None] * initial_size
    
    def create_uncountable_composite(self):
        """
        Create a new uncountable composite vertex (dict).
        Returns: New empty dict
        """
        return {}
    
    def is_coherent(self, vertex_cardinality, label_cardinality):
        """
        Check tail-label coherence.
        Returns: True if vertex and label cardinalities are coherent
        """
        if vertex_cardinality == Cardinality_AlephNull: return label_cardinality == Cardinality_AlephNull
        elif vertex_cardinality == Cardinality_AlephOne: return label_cardinality == Cardinality_AlephOne
        else: return False  # Atomic vertices cannot have arcs


def query_merge_policy_use_mine(path, target_cardinality, source_cardinality):
    """Default merge policy: overwrite if atomic or cardinalities differ, otherwise keep"""
    if source_cardinality == Cardinality_Zero or target_cardinality != source_cardinality: return Merge_Overwrite
    else: return Merge_Keep

def apply_cursor(cursor, target_root, policy_fn, fabric, dict_key_order):
    """Apply a single cursor to target_root, returning modified target_root"""
    path = cursor["path"]
    value = cursor["value"]
    current_path = []
    
    # ROOTED CURSOR CASE (path indicates an atomic cursor)
    if len(path) == 0:
        target_root_cardinality = fabric.get_vertex_cardinality(target_root)

        if value != Cardinality_AlephOne and value != Cardinality_AlephNull: source_cardinality = fabric.get_vertex_cardinality(value)
        else: source_cardinality = value

        decision = policy_fn(current_path, target_root_cardinality, source_cardinality)
        if decision == Merge_Fail: raise Exception("Merge failed at root")
        elif decision == Merge_Keep: return target_root
        elif decision == Merge_Overwrite:
            if source_cardinality == Cardinality_AlephOne: return fabric.create_uncountable_composite()
            elif source_cardinality == Cardinality_AlephNull: return fabric.create_countable_composite()
            else: return value
        else: raise NotImplementedError("Unknown merge decision")
    
    # PRELIMINARY STEP: Handle target_root merging

    target_arc_tail = None          # a virtual arc with the root vertex as a head has no tail (root has no container or label)
    target_arc_label = None         # a virtual arc with the root vertex as a head has no label (root has no container or label)
    target_arc_head = target_root
    target_arc_head_cardinality = fabric.get_vertex_cardinality(target_arc_head)

    #source_arc_tail = None          # a virtual arc with the root vertex as a head has no tail (root has no container or label)
    source_arc_label = None         # a virtual arc with the root vertex as a head has no label (root has no container or label)
    #source_arc_head = None          # a virtual arc with the root vertex as a head has source root head that is unknowable with compact graph paths
    source_arc_head_cardinality = fabric.get_label_cardinality(path[0])

    decision = policy_fn(current_path, target_arc_head_cardinality, source_arc_head_cardinality)
    if decision == Merge_Fail: raise Exception("Merge failed at root preparation")
    elif decision == Merge_Keep: pass
    elif decision == Merge_Overwrite:
        if source_arc_head_cardinality == Cardinality_AlephOne: target_arc_head = target_root = fabric.create_uncountable_composite()
        elif source_arc_head_cardinality == Cardinality_AlephNull: target_arc_head = target_root = fabric.create_countable_composite()
        else: raise Exception("Invalid operation in root preparation")
    else: raise NotImplementedError("Unknown merge decision")
    
    # MAIN LOOP
    for i in range(len(path)):

        target_arc_tail = target_arc_head
        target_arc_label = path[i]
        if fabric.arc_exists(target_arc_tail, target_arc_label):
            target_arc_head = target_arc_tail[target_arc_label]
            target_arc_head_cardinality = fabric.get_vertex_cardinality(target_arc_head)
        else:
            target_arc_head = None
            target_arc_head_cardinality = Cardinality_Void

        #source_arc_tail = None          # a virtual arc with the root vertex as a head has source tail that is unknowable with compact graph paths
        source_arc_label = path[i]
        #source_arc_head = None          # a virtual arc with the root vertex as a head has source head that is unknowable with compact graph paths
        if i < len(path) - 1: source_arc_head_cardinality = fabric.get_label_cardinality(path[i + 1])
        else:
            if value != Cardinality_AlephOne and value != Cardinality_AlephNull: source_arc_head_cardinality = Cardinality_Zero
            else: source_arc_head_cardinality = value

        current_path.append(source_arc_label)
        decision = policy_fn(current_path, target_arc_head_cardinality, source_arc_head_cardinality)
        if decision == Merge_Fail: raise Exception(f"Merge failed at path {current_path}")
        elif decision == Merge_Keep: continue
        elif decision == Merge_Overwrite:
            if source_arc_head_cardinality == Cardinality_AlephOne: target_arc_head = fabric.create_uncountable_composite()
            elif source_arc_head_cardinality == Cardinality_AlephNull: target_arc_head = fabric.create_countable_composite()
            elif source_arc_head_cardinality == Cardinality_Zero: target_arc_head = value
            else: raise NotImplementedError("Unknown source cardinality")
            if isinstance(target_arc_tail, dict) and dict_key_order == DictKeyOrder_LastWins and fabric.arc_exists(target_arc_tail, target_arc_label):
                del target_arc_tail[target_arc_label]
            target_arc_tail[target_arc_label] = target_arc_head
        else: raise NotImplementedError("Unknown merge decision")
    return target_root

def graph_merge(cursors, target_root=None, policy_fn=None, fabric=None, dict_key_order=DictKeyOrder_FirstWins):
    """
    Rebuild graph structure from cursor list
    Args:
        cursors: List of {"path": [...], "value": any} objects
        target_root: Initial target graph (None for empty)
        policy_fn: Callback to resolve path conflicts
        fabric: Fabric instance for vertex operations
    Returns:
        Reconstructed graph structure
    """
    if fabric is None: fabric = JsonFabric()
    if policy_fn is None: policy_fn = query_merge_policy_use_mine
    for cursor in cursors: target_root = apply_cursor(cursor, target_root, policy_fn, fabric, dict_key_order)
    return target_root

def graph_list(data, fabric=None, _path=None):
    """
    Create a list of cursors representing all vertices in the graph.
    Args:
        data: Root vertex to traverse
        fabric: Fabric instance for vertex type recognition
        _path: Internal parameter for recursion
    Returns: List of {"path": [...], "value": vertex} cursors
    """
    if fabric is None: fabric = JsonFabric()
    if _path is None: _path = []
    result = []
    cardinality = fabric.get_vertex_cardinality(data)
    if cardinality == Cardinality_AlephOne:  # Uncountable composite - traverse dict
        if len(data) == 0: result.append({"path": _path, "value": Cardinality_AlephOne})
        else:
            for key, value in data.items():
                result.extend(graph_list(value, fabric, _path + [key]))
    elif cardinality == Cardinality_AlephNull:  # Countable composite - don't traverse
        if len(data) == 0: result.append({"path": _path, "value": Cardinality_AlephNull})
        else: result.append({"path": _path, "value": data})
    else: result.append({"path": _path, "value": data})   # Atomic vertex
    return result

def _encode_component(value):
    """
    Encode a path component into dot-sharp notation.
    
    Args:
        value: string or integer to encode
        
    Returns:
        Encoded component as string or integer
    """
    if isinstance(value, int):
        return value
    
    if len(value) == 0:
        return "\\0"
    
    # Escape dots, backslashes, and sharps
    return value.replace("\\", "\\\\").replace(".", "\\.").replace("#", "\\#")

def _append_component(path, encoded_component):
    """
    Append an encoded component to a dot-sharp path.
    
    Args:
        path: Current path as string, integer, or None
        encoded_component: Component to append as string or integer
        
    Returns:
        New path as string
    """
    if isinstance(encoded_component, int):
        if path is None:
            return f"#{encoded_component}"
        elif isinstance(path, int):
            return f"#{path}#{encoded_component}"
        elif len(path) == 0 or path == "\\0":
            return f"\\0#{encoded_component}"
        else:
            return f"{path}#{encoded_component}"
    else:  # encoded_component is string
        if path is None:
            if len(encoded_component) == 0 or encoded_component == "\\0":
                return "\\0"
            return encoded_component
        elif isinstance(path, int):
            if len(encoded_component) == 0 or encoded_component == "\\0":
                return f"#{path}."
            elif encoded_component.startswith("#"):
                return f"#{path}{encoded_component}"
            else:
                return f"#{path}.{encoded_component}"
        elif len(path) == 0 or path == "\\0":
            if len(encoded_component) == 0 or encoded_component == "\\0":
                return "."
            elif encoded_component.startswith("#"):
                return f"\\0{encoded_component}"
            else:
                return f".{encoded_component}"
        else:
            if len(encoded_component) == 0 or encoded_component == "\\0":
                return f"{path}."
            elif encoded_component.startswith("#"):
                return f"{path}{encoded_component}"
            else:
                return f"{path}.{encoded_component}"

def graph_path_to_dotsharp(path):
    """
    Convert a cursor path (list of strings/integers) to dot-sharp notation.
    
    Args:
        path: List of strings and integers representing a graph path
        
    Returns:
        Dot-sharp encoded path as string
    """
    if len(path) == 0:
        return "\\0"  # Empty path becomes \\0
    
    result = None
    for component in path:
        encoded = _encode_component(component)
        result = _append_component(result, encoded)
    
    return result

def _decode_component(value):
    """
    Decode a dot-sharp notation component.
    
    Args:
        value: string or integer to decode
        
    Returns:
        Decoded component as string or integer
    """
    if isinstance(value, int):
        return value
    
    if value == "\\" or value == "\\0" or value == "":
        return ""
    
    if '\\' not in value:
        return value
    
    # Decode escape sequences
    result = ""
    i = 0
    while i < len(value):
        if value[i] == '\\' and i + 1 < len(value):
            result += value[i + 1]  # Add the escaped character
            i += 2
        else:
            result += value[i]
            i += 1
    
    return result

def _split_by_delimiter(path, delimiter):
    """
    Split path by delimiter, respecting escape sequences.
    
    Args:
        path: String to split
        delimiter: Character to split on ('.' or '#')
        
    Returns:
        List of split components
    """
    if len(path) == 0:
        return [""]
    
    result = []
    current = ""
    i = 0
    
    while i < len(path):
        if path[i] == '\\' and i + 1 < len(path):
            # Escape sequence - add both characters to current
            current += path[i:i+2]
            i += 2
        elif path[i] == delimiter:
            # Found unescaped delimiter
            result.append(current)
            current = ""
            i += 1
        else:
            current += path[i]
            i += 1
    
    result.append(current)
    return result

def dotsharp_to_graph_path(dotsharp_path):
    """
    Parse a dot-sharp notation string into a list of path components.
    
    Args:
        dotsharp_path: Dot-sharp encoded path as string, integer, or None
        
    Returns:
        List of decoded path components (strings and integers)
    """
    if dotsharp_path is None:
        return []
    
    if isinstance(dotsharp_path, int):
        return [dotsharp_path]
    
    if len(dotsharp_path) == 0 or dotsharp_path == "\\0":
        return [""]
    
    if dotsharp_path == "\\":
        return ["\\"]
    
    result = []
    
    # Split by unescaped dots first
    dot_parts = _split_by_delimiter(dotsharp_path, '.')
    
    for i, part in enumerate(dot_parts):
        # Check if this part contains unescaped sharps
        has_unescaped_sharp = False
        j = 0
        while j < len(part):
            if part[j] == '#' and (j == 0 or part[j-1] != '\\'):
                has_unescaped_sharp = True
                break
            elif part[j] == '\\' and j + 1 < len(part):
                j += 2  # Skip escaped character
            else:
                j += 1
        
        if has_unescaped_sharp:
            # Split by unescaped sharps
            sharp_parts = _split_by_delimiter(part, '#')
            
            # First part (before any #) - add if not empty or if this is not first dot part
            if sharp_parts[0] != "" or i != 0:
                result.append(_decode_component(sharp_parts[0]))
            
            # Remaining parts should be integers
            for k in range(1, len(sharp_parts)):
                try:
                    result.append(int(sharp_parts[k]))
                except ValueError:
                    # If not a valid integer, treat as escaped string
                    result.append(_decode_component(sharp_parts[k]))
        else:
            # No unescaped sharps, treat as regular string component
            result.append(_decode_component(part))
    
    return result

# Test the fabric and function
def _run_tests():
    """Run tests to verify graph_list and graph_merge work correctly"""
    fabric = JsonFabric()
    
    # Test round-trip: list -> merge
    data = {"name": "test", "value": 42}
    cursors = graph_list(data, fabric)
    merged = graph_merge(cursors, None, None, fabric)
    assert data == merged, f"Round trip failed: {data} != {merged}"
    
    # Test atomic root
    atomic_cursors = [{"path": [], "value": 100}]
    merged_atomic = graph_merge(atomic_cursors, None, None, fabric)
    assert merged_atomic == 100, f"Atomic root failed: {merged_atomic}"
    
    # Test empty structures
    empty_cursors = [
        {"path": ["empty_dict"], "value": Cardinality_AlephOne},
        {"path": ["empty_list"], "value": Cardinality_AlephNull}
    ]
    merged_empty = graph_merge(empty_cursors, None, None, fabric)
    expected_empty = {"empty_dict": {}, "empty_list": []}
    assert merged_empty == expected_empty, f"Empty structures failed: {merged_empty}"
    
    # Test conflict resolution
    conflict_cursors = [
        {"path": ["config"], "value": 100},
        {"path": ["config"], "value": 200}
    ]
    merged_conflict = graph_merge(conflict_cursors, None, None, fabric)
    assert merged_conflict == {"config": 200}, f"Conflict resolution failed: {merged_conflict}"
    
    # Test with existing target
    existing = {"existing": "data"}
    new_cursors = [{"path": ["new"], "value": "added"}]
    merged_existing = graph_merge(new_cursors, existing, None, fabric)
    expected_existing = {"existing": "data", "new": "added"}
    assert merged_existing == expected_existing, f"Merge into existing failed: {merged_existing}"
    
    # Test nested structures
    data_nested = {
        "name": "test",
        "config": {
            "width": 100,
            "nested": {"deep": "value"}
        },
        "items": [1, 2, 3]
    }
    cursors_nested = graph_list(data_nested, fabric)
    merged_nested = graph_merge(cursors_nested, None, None, fabric)
    assert data_nested == merged_nested, f"Nested round trip failed: {data_nested} != {merged_nested}"

    # Test dot-sharp notation
    test_paths = [
        ([], "\\0"),
        (["a"], "a"),
        ([0], "#0"),
        (["a", "b"], "a.b"),
        ([0, 1], "#0#1"),
        (["a", 0], "a#0"),
        ([0, "b"], "#0.b"),
        ([""], "\\0"),
        (["", ""], "."),
        (["a.b#c\\d"], "a\\.b\\#c\\\\d"),
        (["a", "", "b"], "a..b"),
    ]
    
    for path, expected in test_paths:
        result = graph_path_to_dotsharp(path)
        assert result == expected, f"Dot-sharp encode test failed: {path} -> expected '{expected}', got '{result}'"
    
    # Test dot-sharp parsing (round-trip)
    test_dotsharp_strings = [
        "\\0",
        "a", 
        "#0",
        "a.b",
        "#0#1", 
        "a#0",
        "#0.b",
        ".",
        "a\\.b\\#c\\\\d",
        "a..b"
    ]
    
    for dotsharp_str in test_dotsharp_strings:
        parsed = dotsharp_to_graph_path(dotsharp_str)
        encoded = graph_path_to_dotsharp(parsed)
        assert encoded == dotsharp_str, f"Dot-sharp round-trip failed: '{dotsharp_str}' -> {parsed} -> '{encoded}'"

# Run tests on module load - silent unless they fail
try:
    _run_tests()
except Exception as e:
    print(f"❌ TEST FAILED: {e}")
    raise