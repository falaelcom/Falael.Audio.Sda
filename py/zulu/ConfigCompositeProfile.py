import os
from zulu.ConfigJSCSS import ConfigJSCSS

class ConfigCompositeProfile:
    def __init__(self, profiles_root: str, profile_names: str):
        self.profiles_root = profiles_root
        self.profile_names = profile_names
    
    def load_config(self) -> ConfigJSCSS:
        engine = ConfigJSCSS()
        
        # Parse comma-separated profile names
        parsed_profiles = [name.strip() for name in self.profile_names.split(',')]
        
        for profile in parsed_profiles:
            if not profile:  # Skip empty strings
                continue
                
            profile_dir = os.path.join(self.profiles_root, profile.strip())
            if not os.path.isdir(profile_dir):
                continue
            for filename in sorted(os.listdir(profile_dir)):
                ccp_file_path = os.path.join(profile_dir, filename)
                if filename.endswith(".py"):
                    engine.cascade_py_module(ccp_file_path)
                elif filename.endswith(".json"):
                    engine.cascade_json_file(ccp_file_path)
        
        return engine