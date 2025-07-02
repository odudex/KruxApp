docker run --rm -it \
  -v $(pwd):/home/user/hostcwd \
  -v $HOME/.buildozer:/home/user/.buildozer \
  --entrypoint bash \
  ghcr.io/kivy/buildozer:latest