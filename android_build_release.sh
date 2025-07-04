#!/bin/bash

mkdir -p .buildozer
mkdir -p .gradle

# Load environment variables
source kruxapp.env

# Docker Build Script for Kivy Android
docker run --rm -it \
  -v $(pwd):/home/user/hostcwd \
  -v $(pwd)/.buildozer:/home/user/.buildozer \
  -v $(pwd)/.gradle:/home/user/.gradle \
  -w /home/user/hostcwd \
  -e P4A_RELEASE_KEYSTORE=/home/user/hostcwd/kruxapp-release-key.jks \
  -e P4A_RELEASE_KEYSTORE_PASSWD="$KEYSTORE_PASS" \
  -e P4A_RELEASE_KEYALIAS_PASSWD="$ALIAS_PASS" \
  -e P4A_RELEASE_KEYALIAS="$ALIAS_NAME" \
  ghcr.io/kivy/buildozer:latest \
  android release