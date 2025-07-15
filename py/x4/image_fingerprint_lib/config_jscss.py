import json
import os
from typing import Dict, List, Any, Optional

class ConfigJSCSS:
    """CSS-like JSON configuration engine for image fingerprint layouts"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize with optional config file path"""
        self.rules = {}
        self.config_path = config_path
        if config_path and os.path.exists(config_path):
            self.load_config(config_path)
    
    def load_config(self, config_path: str):
        """Load configuration from JSON file"""
        with open(config_path, 'r', encoding='utf-8') as f:
            self.rules = json.load(f)
    
    def load_config_dict(self, config_dict: Dict[str, Any]):
        """Load configuration from dictionary"""
        self.rules = config_dict
    
    def _parse_selector(self, selector: str) -> List[str]:
        """Parse CSS-like selector into list of classes
        
        Examples:
        "" -> []
        ".tbm" -> ["tbm"]
        ".tbm.zf" -> ["tbm", "zf"]
        """
        if not selector.strip():
            return []
        
        # Remove leading/trailing whitespace and split by dots
        classes = [cls.strip() for cls in selector.split('.') if cls.strip()]
        return classes
    
    def _calculate_specificity(self, selector: str) -> int:
        """Calculate specificity of a selector (number of classes)"""
        classes = self._parse_selector(selector)
        return len(classes)
    
    def _selector_matches(self, selector: str, target_classes: List[str]) -> bool:
        """Check if selector matches target classes
        
        Args:
            selector: CSS-like selector string (e.g., ".tbm.zf")
            target_classes: List of classes to match against (e.g., ["tbm", "zf"])
        
        Returns:
            True if all selector classes are present in target_classes
        """
        selector_classes = self._parse_selector(selector)
        
        # Empty selector (root) always matches
        if not selector_classes:
            return True
        
        # All selector classes must be present in target_classes
        return all(cls in target_classes for cls in selector_classes)
    
    def _sort_matching_rules(self, target_classes: List[str]) -> List[tuple]:
        """Sort matching rules by specificity and original order
        
        Returns:
            List of (selector, rule_dict, original_index) tuples sorted by:
            1. Specificity (ascending - least specific first)
            2. Original order (ascending - preserve JSON order for same specificity)
        """
        matching_rules = []
        
        for idx, (selector, rule_dict) in enumerate(self.rules.items()):
            if self._selector_matches(selector, target_classes):
                specificity = self._calculate_specificity(selector)
                matching_rules.append((selector, rule_dict, specificity, idx))
        
        # Sort by specificity first, then by original index
        matching_rules.sort(key=lambda x: (x[2], x[3]))
        
        return [(selector, rule_dict, idx) for selector, rule_dict, specificity, idx in matching_rules]
    
    def get_config(self, permutation: str, z_mode: str) -> Dict[str, Any]:
        """Get resolved configuration for specific permutation and z-mode
        
        Args:
            permutation: Three-letter permutation like "tbm", "mtb", etc.
            z_mode: Z-rendering mode like "zich", "zicv", "zf"
        
        Returns:
            Merged configuration dictionary with cascaded values
        """
        target_classes = [permutation.lower(), z_mode.lower()]
        matching_rules = self._sort_matching_rules(target_classes)
        
        # Build final config by applying rules in order (least to most specific)
        final_config = {}
        
        for selector, rule_dict, _ in matching_rules:
            # Apply this rule's properties to final config
            final_config.update(rule_dict)
        
        return final_config
    
    def get_available_permutations(self) -> List[str]:
        """Get list of available permutation classes from rules"""
        permutations = set()
        
        # Known permutation patterns (3-letter combinations of t, b, m)
        known_perms = ["tbm", "tmb", "btm", "bmt", "mtb", "mbt"]
        
        for selector in self.rules.keys():
            classes = self._parse_selector(selector)
            for cls in classes:
                if cls in known_perms:
                    permutations.add(cls)
        
        return sorted(list(permutations))
    
    def get_available_z_modes(self) -> List[str]:
        """Get list of available z-mode classes from rules"""
        z_modes = set()
        
        # Known z-mode patterns
        known_z_modes = ["zich", "zicv", "zf"]
        
        for selector in self.rules.keys():
            classes = self._parse_selector(selector)
            for cls in classes:
                if cls in known_z_modes:
                    z_modes.add(cls)
        
        return sorted(list(z_modes))
    
    def debug_matching_rules(self, permutation: str, z_mode: str) -> List[Dict[str, Any]]:
        """Debug function to show which rules match and their application order"""
        target_classes = [permutation.lower(), z_mode.lower()]
        matching_rules = self._sort_matching_rules(target_classes)
        
        debug_info = []
        for selector, rule_dict, original_idx in matching_rules:
            specificity = self._calculate_specificity(selector)
            debug_info.append({
                "selector": selector,
                "specificity": specificity,
                "original_index": original_idx,
                "properties": list(rule_dict.keys()),
                "rule": rule_dict
            })
        
        return debug_info


# Convenience functions for direct usage
_global_config_engine = None

def init_config(config_path: str = None, config_dict: Dict[str, Any] = None):
    """Initialize global configuration engine"""
    global _global_config_engine
    _global_config_engine = ConfigJSCSS()
    
    if config_path:
        _global_config_engine.load_config(config_path)
    elif config_dict:
        _global_config_engine.load_config_dict(config_dict)

def get_config(permutation: str, z_mode: str) -> Dict[str, Any]:
    """Get configuration for specific layout combination"""
    if _global_config_engine is None:
        raise RuntimeError("Configuration not initialized. Call init_config() first.")
    
    return _global_config_engine.get_config(permutation, z_mode)

def debug_config(permutation: str, z_mode: str) -> List[Dict[str, Any]]:
    """Debug configuration matching for specific layout combination"""
    if _global_config_engine is None:
        raise RuntimeError("Configuration not initialized. Call init_config() first.")
    
    return _global_config_engine.debug_matching_rules(permutation, z_mode)


# Example usage and testing
if __name__ == "__main__":
    # Example configuration
    example_config = {
        "": {  # Root defaults
            "DATAPOINT_WIDTH_PX": 48,
            "DATAPOINT_HEIGHT_PX": 48,
            "page_top_padding": 2,
            "page_left_padding": 2,
            "horizontal_label_font_ratio": 0.4
        },
        ".tbm": {  # Time-Band-Metric layout
            "DATAPOINT_WIDTH_PX": 40,
            "page_top_padding": 1.5
        },
        ".zf": {  # Z-as-file mode
            "DATAPOINT_WIDTH_PX": 35,
            "page_left_padding": 1.5
        },
        ".tbm.zf": {  # Most specific: tbm layout with z-as-file
            "page_top_padding": 1.0,
            "horizontal_label_font_ratio": 0.35
        },
        ".zf.tbm": {  # Same specificity as above, should override due to order
            "page_top_padding": 0.8
        }
    }
    
    # Test the engine
    engine = ConfigJSCSS()
    engine.load_config_dict(example_config)
    
    # Get config for tbm + zf combination
    config = engine.get_config("tbm", "zf")
    print("Final config for tbm+zf:")
    for key, value in sorted(config.items()):
        print(f"  {key}: {value}")
    
    print("\nDebug info:")
    debug_info = engine.debug_matching_rules("tbm", "zf")
    for rule in debug_info:
        print(f"  {rule['selector']} (specificity: {rule['specificity']}) -> {rule['properties']}")