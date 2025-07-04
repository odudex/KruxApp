#!/bin/bash

mkdir -p ~/.buildozer
mkdir -p ~/.gradle

# Docker Build Script for Kivy Android
docker run --rm -it \
  -v $(pwd):/home/user/hostcwd \
  -v $(pwd)/.buildozer:/home/user/.buildozer \
  -v $(pwd)/.gradle:/home/user/.gradle \
  -w /home/user/hostcwd \
  ghcr.io/kivy/buildozer:latest \
  android debug