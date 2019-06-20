#!/bin/bash
set -euxo pipefail

function cmakebuild() {
  cd $1
  mkdir build
  cd build
  cmake ..
  make
  make install
  cd ../..
  rm -rf $1
}

cd /tmp

STATIC_PACKAGES="libusb fftw"
BUILD_PACKAGES="git cmake make patch wget sudo udev gcc g++ libusb-dev fftw-dev"

apk add --no-cache $STATIC_PACKAGES
apk add --no-cache --virtual .build-deps $BUILD_PACKAGES

git clone https://github.com/mossmann/hackrf.git
cd hackrf
cmakebuild host
cd ..
rm -rf hackrf

git clone https://github.com/pothosware/SoapyHackRF.git
cmakebuild SoapyHackRF

apk del .build-deps