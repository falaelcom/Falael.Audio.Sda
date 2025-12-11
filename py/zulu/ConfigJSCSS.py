import json
import importlib.util
from typing import  List, Any, Optional, Union
from xmlrpc.client import Boolean
from zulu.graph import DictKeyOrder_LastWins, JsonFabric, graph_list, graph_merge, dotsharp_to_graph_path

class ConfigJSCSS:
    def __init__(self, source: Optional[Union[List[dict], dict, list]] = None, dotSharpLabels: Boolean = True):
        self.fabric = JsonFabric()
        self.cursor_list = []
        self.dirty_flag = False
        self.data = []

        if source is None:
            return
        elif isinstance(source, list) and all(isinstance(x, dict) and "path" in x for x in source):
            self.cursor_list = self._process_cursors_with_dotsharp(source, dotSharpLabels)
            self.dirty_flag = True
        elif isinstance(source, (dict, list)):
            self.cascade_graph(source, dotSharpLabels)
        else:
            raise TypeError("Invalid source type for ConfigJSCSS")

    def _process_cursors_with_dotsharp(self, cursors: List[dict], dotSharpLabels: Boolean) -> List[dict]:
        """Process cursors to expand dot-sharp labels if dotSharpLabels is True"""
        if not dotSharpLabels:
            return cursors
        
        processed_cursors = []
        for cursor in cursors:
            original_path = cursor["path"]
            value = cursor["value"]
            
            # Expand each label in the path using dot-sharp parsing
            expanded_path = []
            for label in original_path:
                parsed_components = dotsharp_to_graph_path(label)
                expanded_path.extend(parsed_components)
            
            processed_cursors.append({
                "path": expanded_path,
                "value": value
            })
        
        return processed_cursors

    def cascade_graph(self, obj: Any, dotSharpLabels: Boolean = True) -> None:
        cursors = graph_list(obj, self.fabric)
        processed_cursors = self._process_cursors_with_dotsharp(cursors, dotSharpLabels)
        self.cursor_list.extend(processed_cursors)
        self.dirty_flag = True

    def cascade_json(self, json_str: str, dotSharpLabels: Boolean = True) -> None:
        parsed_obj = json.loads(json_str)
        self.cascade_graph(parsed_obj, dotSharpLabels)

    def cascade_json_file(self, json_file_path: str, dotSharpLabels: Boolean = True) -> None:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            json_content = f.read()
        self.cascade_json(json_content, dotSharpLabels)

    def cascade_py_module(self, py_module_file_path: str, dotSharpLabels: Boolean = True) -> None:
        spec = importlib.util.spec_from_file_location("temp_config_module", py_module_file_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.cascade_graph(mod.CONFIG, dotSharpLabels)

    def to_graph(self) -> Union[dict, list]:
        if self.dirty_flag:
            merged_graph = graph_merge(self.cursor_list, target_root=None, policy_fn=None, fabric=self.fabric, dict_key_order=DictKeyOrder_LastWins)
            if not merged_graph: merged_graph = {}
            self.data = merged_graph
            self.dirty_flag = False
        return self.data

    def query(self, path_filter: Optional[str] = None, selector: Optional[str] = None) -> 'ConfigJSCSS':
        selected_cursors = []

        for cursor in self.cursor_list:
            full_path = cursor["path"]

            assert len(full_path) >= 1
            path = full_path[:-1]
            field_name = full_path[-1]

            if path_filter:
                prefix_path = dotsharp_to_graph_path(path_filter)
                if len(path) < len(prefix_path): continue
                if not self._path_matches_with_wildcards(path, prefix_path): continue
                path = path[len(prefix_path):]

            if len(path) == 1 and path[0] == "*": path = []

            if selector:
                selector_as_path = dotsharp_to_graph_path(selector)
                if not self._is_ordered_subset(path, selector_as_path): continue
                path = [element for element in path if element not in selector_as_path]

            selected_cursors.append({
                "path": path + [field_name],
                "value": cursor["value"]
            })

        return ConfigJSCSS(selected_cursors)

    def _path_matches_with_wildcards(self, cursor_path: List[str], filter_path: List[str]) -> bool:
        """
        Check if cursor_path matches filter_path, treating "*" in cursor_path as wildcards
        that can match any component in filter_path.
        """
        if len(cursor_path) < len(filter_path):
            return False
    
        # Check if the first len(filter_path) components of cursor_path match filter_path
        for i in range(len(filter_path)):
            cursor_component = cursor_path[i]
            filter_component = filter_path[i]
        
            # "*" in cursor path matches any filter component
            if cursor_component == "*":
                continue
            # Exact match required for non-wildcard components
            elif cursor_component != filter_component:
                return False
    
        return True

    def _is_ordered_subset(self, cursor_path: List[str], selector: List[str]) -> bool:
        if not cursor_path:
            return True
        pos = 0
        for label in cursor_path:
            while pos < len(selector) and selector[pos] != label:
                pos += 1
            if pos == len(selector):
                return False
            pos += 1
        return True

def run_tests():
    root = {
        "*": {
            "a": 1,
            "b": 2
        },
        "x": {
            "b": 3
        },
        "x.y": {
            "c": 4
        },
        "module.section": {
            "alpha": 10
        },
        "module.section.sub": {
            "beta": 20
        },
        "config.audio.effects": {
            "reverb": True
        },
        "dark.mobile": {
            "contrast": "high"
        },
        "mobile.dark": {
            "contrast": "medium"
        }
    }

    config = ConfigJSCSS(root, dotSharpLabels=True)

    flat = config.query(selector="x.y")
    flat = flat.to_graph()
    assert flat == {"a": 1, "b": 3, "c": 4}

    subtree = config.query(path_filter="module.section").to_graph()
    assert subtree == {"alpha": 10, "sub": {"beta": 20}}

    full = config.query().to_graph()
    assert "a" in full and "module" in full and "config" in full

    sel = config.query(selector="dark.mobile").to_graph()
    assert sel["contrast"] == "high"

    sel_fail = config.query(selector="mobile.dark").to_graph()
    assert sel_fail["contrast"] == "medium"

    sel_empty = config.query(selector="nonexistent").to_graph()
    assert sel_empty == {"a": 1, "b": 2}

    empty_sub = config.query(path_filter="non.existent").to_graph()
    assert empty_sub == {}

    scoped = config.query(path_filter="config.audio", selector="effects").to_graph()
    assert scoped == {"reverb": True}

run_tests()