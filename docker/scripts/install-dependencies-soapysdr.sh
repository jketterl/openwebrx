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

STATIC_PACKAGES="libudev1"
BUILD_PACKAGES="git cmake make patch wget sudo gcc g++"

apt-get update
apt-get -y install --no-install-recommends $STATIC_PACKAGES $BUILD_PACKAGES

git clone https://github.com/pothosware/SoapySDR
cmakebuild SoapySDR f722f9ce5b629c3c44401a9bf628b3f8e67a9695

SUDO_FORCE_REMOVE=yes apt-get -y purge --autoremove $BUILD_PACKAGES
apt-get clean
rm -rf /var/lib/apt/lists/*
