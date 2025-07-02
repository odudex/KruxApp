#!/bin/bash

# Docker Build Script for Kivy Android
docker run --rm -it \
  -v $(pwd):/home/user/hostcwd \
  -v $HOME/.buildozer:/home/user/.buildozer \
  -w /home/user/hostcwd \
  ghcr.io/kivy/buildozer:latest \
  android debug