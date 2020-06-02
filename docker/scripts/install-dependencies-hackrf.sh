#!/bin/bash
set -euxo pipefail
export MAKEFLAGS="-j4"

function cmakebuild() {
  cd $1
  if [[ ! -z "${2:-}" ]]; then
    git checkout $2
  fi
  mkdir build
  cd build
  cmake ..
  make
  make install
  cd ../..
  rm -rf $1
}

cd /tmp

STATIC_PACKAGES="libusb-1.0-0 libfftw3-3 udev"
BUILD_PACKAGES="git cmake make patch wget sudo gcc g++ libusb-1.0-0-dev libfftw3-dev pkg-config"

apt-get update
apt-get -y install --no-install-recommends $STATIC_PACKAGES $BUILD_PACKAGES

git clone https://github.com/mossmann/hackrf.git
cd hackrf
git checkout 43e6f99fe8543094d18ff3a6550ed2066c398862
cmakebuild host
cd ..
rm -rf hackrf

git clone https://github.com/pothosware/SoapyHackRF.git
cmakebuild SoapyHackRF 3c514cecd3dd2fdf4794aebc96c482940c11d7ff

SUDO_FORCE_REMOVE=yes apt-get -y purge --autoremove $BUILD_PACKAGES
apt-get clean
rm -rf /var/lib/apt/lists/*
