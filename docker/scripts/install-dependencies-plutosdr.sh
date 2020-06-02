#!/usr/bin/env bash
set -euo pipefail
export MAKEFLAGS="-j4"

function cmakebuild() {
  cd $1
  if [[ ! -z "${2:-}" ]]; then
    git checkout $2
  fi
  mkdir build
  cd build
  cmake .. ${3:-}
  make
  make install
  cd ../..
  rm -rf $1
}

cd /tmp

STATIC_PACKAGES="libusb-1.0-0 libxml2"
BUILD_PACKAGES="git libusb-1.0-0-dev cmake make gcc g++ libxml2-dev flex bison"

apt-get update
apt-get -y install --no-install-recommends $STATIC_PACKAGES $BUILD_PACKAGES

git clone https://github.com/analogdevicesinc/libiio.git
cmakebuild libiio 5f5af2e417129ad8f4e05fc5c1b730f0694dca12 -DCMAKE_INSTALL_PREFIX=/usr/local

git clone https://github.com/analogdevicesinc/libad9361-iio.git
cmakebuild libad9361-iio 8ac95f3325c18c2e34cd9cfd49c7b63d69a0a9d2

git clone https://github.com/pothosware/SoapyPlutoSDR.git
cmakebuild SoapyPlutoSDR c88b7f5bac1e5785f212f9a7c6ce8fef64eb719e

apt-get -y purge --autoremove $BUILD_PACKAGES
apt-get clean
rm -rf /var/lib/apt/lists/*
