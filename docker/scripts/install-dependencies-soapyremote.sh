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
  cmake ..
  make
  make install
  cd ../..
  rm -rf $1
}

cd /tmp

STATIC_PACKAGES="avahi-daemon libavahi-client3"
BUILD_PACKAGES="git cmake make gcc g++ libavahi-client-dev"

apt-get update
apt-get -y install --no-install-recommends $STATIC_PACKAGES $BUILD_PACKAGES

git clone https://github.com/pothosware/SoapyRemote.git
cmakebuild SoapyRemote 6d9bd820da470cfe7b27b2e6946af93cfece448f

apt-get -y purge --autoremove $BUILD_PACKAGES
apt-get clean
rm -rf /var/lib/apt/lists/*
