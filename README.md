# Falael.Audio.Sda

## Installation

### Requirements

- Requires Python to run. Developed and tested with `Python 3.9.13`.

- Uses SOX for audio processing. Developed and tested with `sox-14.4.2-20250323-x64`, downloaded from https://www.rarewares.org/files/others/, file `sox-14.4.2-x64.zip  2025-03-23 03:15  1.5M`, full download link of the windows distribution: https://www.rarewares.org/files/others/sox-14.4.2-x64.zip
	- Unzip the binary `sox.exe` file under `win32/sox-14.4.2-20250323-x64`

## Windows (CLI)
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

## POSIX

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

