# Falael.Audio.Sda

## Installation

### Requirements

- Requires Python to run. Developed and tested with `Python 3.9.13`.

- Uses SOX for audio processing. Developed and tested with `sox-14.4.2-20250323-x64`, downloaded from https://www.rarewares.org/files/others/, file `sox-14.4.2-x64.zip  2025-03-23 03:15  1.5M`, full download link of the windows distribution: https://www.rarewares.org/files/others/sox-14.4.2-x64.zip
	- Unzip the binary `sox.exe` file under `win32/sox-14.4.2-20250323-x64`

### Windows (CLI)
```
mkdir c:\Falael.Audio.Sda
cd c:\Falael.Audio.Sda
rem checkout the codebase from github in this directory so that `main.py` is in `c:\Falael.Audio.Sda\py\`
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
- src\sample.mp3
--- split
--- stereo_correlation
--- stereo_width
--- stereo_phase
--- sparkle
--- harmonics
--- harmonics_full_spectrum
--- freq_response
--- dynamics
--- dynamics_full_spectrum
--- quantization
--- quantization_full_spectrum
--- dynamic_range
--- audio_quality
--- image_fingerprint
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

- `py/main.py::MODULES` - a list of modules to run if no JSON data is available for the respective modules
- `py/main.py::ALWAYS_RUN` - a list of modules to run despite the fact that JSON data is available for the respective modules
- `py/main.py::SRC_DIR` -  the name of the source directory; the app will take each `*.wav; *.mp3; *.flac` (as listed in `py/main.py::def get_input_files`) file from this directory and depending on existing data, run all, a part of none of the analysis modules
- `py/main.py::OUT_DIR` -  the name of the output directory; the app will create subdirectories and files under this directory
- `py/main.py::CONFIG` -  module configuration; chart layouts and normalization functions (coloring) are designed to match this configuration; if you change this configuration, you might need to also adjust chart layouts (`py/x4/image_fingerprint_lib/config.py`) and normalization functions (`py/x4/image_fingerprint_lib/metrics.py`) to get concise results
- `py/x4/image_fingerprint_lib/config.py` - chart layout and visuals configuration
- `py/x4/image_fingerprint_lib/metrics.py` - metric normalization functions, labels and rendering order

#### Output

Find the JSON and charts under the directory, configured as output directory (by defailt `./out`):

- `./out/<track-file-name.ext>/media/<track-file-name.ext>` - copy of the source file
- `./out/<track-file-name.ext>/media/<track-file-name.ext>.NNN.<ext>` - the source file in 30s chunks
- `./out/<track-file-name.ext>/<track-file-name.ext>.json` - raw metrics data
- `./out/<track-file-name.ext>/fingerprint/*.png` - multiple perspectives charting a selected subset of the metrics data; meaning of the file naming abbreviations:
	- `.btm, .bmt, .tbm, .tmb, .mbt, .mtb` - mapping of the result space dimensions to the X, Y and Z axes (btm means X=Bands, Y=Time/Chunks, Z=Metrics)
	- `.zich` - Z-mode is intra-cell rows (datapoints are stacked horizontally)
	- `.zicv` - Z-mode is intra-cell columns (datapoints are stacked vertically)
	- no `.zic*` - Z-mode is file names, multiple images are generated per chart (e.g. `.btm` w/ no `.zic*` means X=Bands and Y=Time/Chunks drawn in a separate image file for each Z=Metrics, i.e. `btm.audio_quality--avg_sinad_db.sample.mp3.png`, `btm.audio_quality--quantization_efficiency.sample.mp3.png` etc.)
	
File names are designed in a way that makes copying the output for multiple tracks into a single directory and visually comparing charts with an image viewer sorting files by names.

## Sample Woutput

- c:\repos\Falael.CODE\code\Falael\Falael.Audio.Sda\pub\github\sample\sample.mp3.json

## Metrics Documentation

https://github.com/falaelcom/Falael.Audio.Sda/blob/trunk/metric-reference.md

Might want to download it and view with a dedicated MD viewer for better experience.

## Resources

- Markdown Viewer for Windows - https://www.softpedia.com/get/Office-tools/Other-Office-Tools/Markdown-Viewer-c3er.shtml

