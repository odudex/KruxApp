# Running Krux on your PC Through Kivy
This was the steps to run and build Krux APK on a fresh Ubuntu environment

## Install Poetry
This project manage dependencies through Poetry, install it accordingly to recommended instructions
https://python-poetry.org/docs/

## Create Virtual environment and Install Dependencies
```
poetry install
```

## Run the App
```
poetry run python main.py
```

# Build the APK with Docker and Buildozer
It is very complicated to get a Kivy-Buildozer toolchain settled and working, so the best is to use a Docker container for building the APK.

Just install Docker and run:

```
android_build.sh
```
The resulting apk will be available in `bin` folder
