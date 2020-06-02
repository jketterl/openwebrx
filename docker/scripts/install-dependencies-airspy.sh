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

STATIC_PACKAGES="libusb-1.0-0"
BUILD_PACKAGES="git libusb-1.0-0-dev cmake make gcc g++ pkg-config"

apt-get update
apt-get -y install --no-install-recommends $STATIC_PACKAGES $BUILD_PACKAGES

git clone https://github.com/airspy/airspyone_host.git
cmakebuild airspyone_host bceca18f9e3a5f89cff78c4d949c71771d92dfd3

git clone https://github.com/pothosware/SoapyAirspy.git
cmakebuild SoapyAirspy 10d697b209e7f1acc8b2c8d24851d46170ef77e3

git clone https://github.com/airspy/airspyhf.git
cmakebuild airspyhf 613852a2bb64af42690bf9be2201826af69a9475

git clone https://github.com/pothosware/SoapyAirspyHF.git
cmakebuild SoapyAirspyHF 81ca737bb044dd930a9de738bced1e4915491f1b

apt-get -y purge --autoremove $BUILD_PACKAGES
apt-get clean
rm -rf /var/lib/apt/lists/*
