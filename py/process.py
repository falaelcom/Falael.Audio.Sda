import pipelines

# select the pipeline to run and a configuation profile to use; 
# cascade multiple configuation profiles by specifying their names as a coma separated list, e.g. "00-default my-profile"
# NOTE: not all pipelines will run out of the box, and their code might need adjustments; `pipeline_fingerprint_debug` and `pipeline_restore_stereo` are guaranteed to run.

PATHS_DEFAULT = { "src": "../data/default/src", "tmp": "../data/default/tmp", "out": "../data/default/out", "cache": "/data/sda/_sda_cache" }
PATHS_REPAIR = { "src": "../data/repair/src", "tmp": "../data/repair/tmp", "out": "../data/repair/out", "cache": "/data/sda/_sda_cache" }
PATHS_INSPECT = { "src": "../data/inspect/src", "tmp": "../data/inspect/tmp", "out": "../data/inspect/out", "cache": "/data/sda/_sda_cache" }

# pipelines.pipeline_debug.run("config_profiles", "00-default", PATHS_DEFAULT)

## pipelines.pipeline_channels_debug.run("config_profiles", "00-default, 01-brief", PATHS_INSPECT)
# pipelines.pipeline_channels_debug.run("config_profiles", "00-default", PATHS_INSPECT)

# pipelines.pipeline_fingerprint.run("config_profiles", "00-default", PATHS_DEFAULT)
# pipelines.pipeline_fingerprint_debug.run("config_profiles", "00-default, 01-brief", PATHS_INSPECT)
# pipelines.pipeline_fingerprint.run("config_profiles", "00-default, 01-brief", PATHS_INSPECT)
# pipelines.pipeline_experiment.run("config_profiles", "00-default, exp-reverb-01", PATHS_DEFAULT)
# pipelines.pipeline_experiment.run("config_profiles", "00-default, exp-reverb-02", PATHS_DEFAULT)

# full inspect
pipelines.pipeline_fingerprint_debug.run("config_profiles", "00-default", PATHS_INSPECT)

# repair SDA
## pipelines.pipeline_restore_stereo.run("config_profiles", "00-default, 01-repair, 03-repair-0008-STNT-The-Clowns-Shining-Ass", PATHS_REPAIR)
