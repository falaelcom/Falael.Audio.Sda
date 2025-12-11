# Falael.Audio.Sda

## Targeted Audience

Software developers. Running this tool requires programming skills to configure and adapt to specific requirements.

## Installation

> _NOTE: The following instructions have rarely been tested on a single dev machine only; might need to improvise in case of unexpected errors._

### Requirements

- Requires Python to run. Developed and tested with `Python 3.9.13`.

- Uses SOX for some types of audio processing. Developed and tested with `sox-14.4.2-20250323-x64`, downloaded from https://www.rarewares.org/files/others/, file `sox-14.4.2-x64.zip  2025-03-23 03:15  1.5M`, full download link of the windows sox distribution: https://www.rarewares.org/files/others/sox-14.4.2-x64.zip
	- Unzip the binary `sox.exe` file under `win32/sox-14.4.2-20250323-x64`

### Windows (CLI)
```
mkdir c:\Falael.Audio.Sda
cd c:\Falael.Audio.Sda
rem checkout the codebase from github in this directory so that `main.py` appears in `c:\Falael.Audio.Sda\py\`
cd py
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install --force-reinstall -r requirements.txt
rem for some reason spectra is not installed via requirements.txt
pip install spectra
python main.py
```

After runnign `python main.py`, if installation was successful the following output will incrementally appear (processing takes time):

```
- ../data/inspect/src\sample.mp3
-------------------------------------------------------------------------
--- partition                                | PROC   | 16 wks |
----- Channel_Mix...

00:03.541
--- base_stereo_width                        | THRD   | 16 wks | 00:15.409
--- base_stereo_phase                        | PROC   | 16 wks | 00:26.073
--- base_stereo_correlation                  | THRD   | 16 wks | 00:15.149
--- base_sparkle                             | THRD   | 16 wks | 00:03.029
--- base_freq_response                       | THRD   | 16 wks | 00:00.915
--- base_dynamics                            | THRD   | 16 wks | 00:08.356
--- base_dynamics_fullspectrum               | THRD   | 16 wks | 00:00.309
--- base_harmonics                           | PROC   | 16 wks | 00:12.198
--- base_harmonics_fullspectrum              | THRD   | 16 wks | 00:00.813
--- base_quantization                        | PROC   | 16 wks | 00:36.019
--- base_quantization_fullspectrum           | PROC   | 16 wks | 00:07.758
--- calc_dynamic_range                       | PROC   | 16 wks | 00:00.002
--- calc_audio_quality                       | PROC   | 16 wks | 00:00.002
--- image_fingerprint                        | THRD   | 16 wks | 00:00.532
```

See __Output__ below for info on the output of the app and where to find it.

The sample "sample.mp3" file contains the song "Samovilla of Collective Unreal - One More Flight" which has been created and produced by me under the name of Dan Loveschmidt and as part of this project is also covered by the MIT license.

### POSIX

The installation process is expected to be trivial. See sox __Configuration__ below.

### Configuration

#### After Install

- `py/main.py::CONFIG::"split::sox_path": r"..\win32\sox-14.4.2-20250323-x64\sox.exe",` 
	- on Windows - you'll need to get `sox.exe` as described in the requirements section above, and extract `sox.exe` as `..\win32\sox-14.4.2-20250323-x64\sox.exe`.
	- requires adjustment for linux installs; needs to point to your sox executable.

#### Customization

**Processors**

- Every separate operation done on either audio data or outupt data from a previous operation is implemented as a separate Python module and is called processor.
	- `processors_transform` - generates new audio files, such as time-split chunks, restored audio etc.
	- `processors_metrics` - analyses audio signal and/or preexisting metrics output and generates new data, for ex. stereo width, dynamic range etc.
	- `processors_visualization` - renders existing metrics as charts (`.png` files), for ex. audio fingerprint.
- Processors are invoked from manually authored pipelines, see next.

**Pipelines**

- Sound metric generation and signal transformation are performed by manually written pipelines, allowing for full customization of the process. Pipelines define, which processors should run, which output data should be collected, and might optionally overwrite any configuration field. 
- Pipelines are aggregated as Python modules under the `pipelines/` directory, which readily several experimental and production pipelines (some might be out of sync with the current codebase and might not work without adjustment).
- Tested pipelines guaranteed to run successfully out of the box are `pipeline_fingerprint_debug.py` and `pipeline_restore_stereo.py`.
- Which pipeline runs is manually coded in `process.py`, with `pipeline_fingerprint_debug` being currently selected.
- Q: What code do I put in a pipeline? A: The main loop iterating source files, processor running and data collection code, any other code you might need for the pipeline to do exactly the job you need. Examine `pipeline_restore_stereo.py` as a working sample.
- Q: Why manual pipelines? A: Allows for granular control over pipeline logic based on specific needs w/o the need for a complex pluggable architecture.
- Q: Does the pipeline provide also full or partial configuration of processors? A: It might, overriding the values provided by the configuration engine, see Configuration Profiles next. It's a decision left for the developer.

**Configuration Profiles**

- This app uses cascading configuration profiles (see the `config_profiles` dir) to produce the effective runtime; each `config_profiles/*` subdir defines a profile. 
- Configuration profiles are manually referenced by name in `process.py`.
- Multiple config profiles are cascaded left to right, with "last wins" overwriting of config properties.
- Profile lists usually start with `"00-default"`, as this profile defines sane default values for all processors.
- A single profile might contain multiple files, which are cascaded in alphabetical order (if order matters, use `"NN-"` prefixes to enforce it).
- Q: Do I need to create new configuration profiles? A: Depends on the needs. If existing profiles match requirements, use them. Otherwise use `00-default` as a base, maybe also other existing profiles, and create new profiles to override only the configuration you need to change.
- Q: Can I create profiles outside the source tree, to separate codebase from my costomizations? A: Not out of the box, but you might fork the repo and add this feat. Same is valid for changes made to `process.py`.

**Using the correct combination**

- The recommended way to create and configure pipelines is to leave most configuration to the config engine. This allows for cross-matching pipelines with config profiles. See `process.py`.
- So, the single run function and configuration comes down to combining a pipeline with one or more cascading config profiles, and an arg for the `paths` param, defining the `src`, `tmp`, `out` and `cache` directories. See `process.py`.

**Cache**

- All processors support caching. Cache keys are built based on input audio file timestamps and processor effective config.
- A cache directory must always be specified, preferably on a very fast storage device (e.g. fast SSD) with lots of space - audio processing generates large cache.
- No automatic cache cleanup of any kind has been implemented - might need to delete the whole cache from time to time and wait for it to be repopulated on subsequent operations.

#### Output

The audio, JSON and image output appear as configured in `process.py`, and used by the respective pipeline (pipelines usually create subdirs to the main output directory).
	
Available pipelines always delete output directories before a run, populating them with either new or cached files.

## Metrics

To understand metrics, read the respective Python modules, or use AI to summarise metric code and provide you with details such as config value meaning and metric value interpretation.

## Visualization

To enable more views on the 4D metrics data, edit `FINGERPRINT_OPTIONS.image_types` in `pipeline_fingerprint_debug.py` (it currently renders a single view), or simply remove this option field to get all possible views.

## Sample Output (src/sample.mp3)

- Input Audio - https://github.com/falaelcom/Falael.Audio.Sda/blob/trunk/sample/src/sample.mp3
- Fingerprint JSON - https://github.com/falaelcom/Falael.Audio.Sda/blob/trunk/sample/out/sample.mp3/metrics.json
- Fingerprint Charts - https://github.com/falaelcom/Falael.Audio.Sda/blob/trunk/sample/out/sample.mp3/images-fingerprint/bmt.zich.sample.mp3.png

![bmt.zich.sample.mp3.png](https://github.com/falaelcom/Falael.Audio.Sda/blob/trunk/sample/out/sample.mp3/images-fingerprint/bmt.zich.sample.mp3.png)

## Resources

- Markdown Viewer for Windows - https://www.softpedia.com/get/Office-tools/Other-Office-Tools/Markdown-Viewer-c3er.shtml

