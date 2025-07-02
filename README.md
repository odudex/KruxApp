# About Krux App
Krux Android app is intended for learning about Krux and Bitcoin air-gapped transactions. Due to many possible vulnerabilities inherent in phones such as the lack of control of the OS, libraries and hardware peripherals, Krux app should NOT be used to manage wallets containing savings or important keys and mnemonics. For that, a dedicated device is recommended.

## Warning!
The app code is poorly tested and maintained. APK signatures and authorship are not yet managed. Users may need to delete older versions to be able to update, and it's very likely stored information, like settings and encrypted mnemonics will be lost on updates.

[Learn more about Krux](https://selfcustody.github.io/krux/getting-started/)

[Krux main repository](https://github.com/selfcustody/krux)

# Running Krux on your PC Through Kivy
These are the steps to run and build Krux APK

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

Just install Docker:

https://docs.docker.com/get-started/get-docker/

Then run:

```
android_build.sh
```

The resulting apk will be available in `bin` folder

# TODO
- Better structure/link submodules
- Improve documentation
- Reduce code customizations for Android
