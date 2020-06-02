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

STATIC_PACKAGES="libusb-1.0.0 udev"
BUILD_PACKAGES="git cmake make patch wget sudo gcc g++ libusb-1.0-0-dev"

apt-get update
apt-get -y install --no-install-recommends $STATIC_PACKAGES $BUILD_PACKAGES

ARCH=$(uname -m)

case $ARCH in
  x86_64)
    BINARY=SDRplay_RSP_API-Linux-3.07.1.run
    ;;
  armv*)
    BINARY=SDRplay_RSP_API-ARM32-3.07.2.run
    ;;
  aarch64)
    BINARY=SDRplay_RSP_API-ARM64-3.07.1.run
    ;;
esac

wget https://www.sdrplay.com/software/$BINARY
sh $BINARY --noexec --target sdrplay
patch --verbose -Np0 < /install-lib.$ARCH.patch

cd sdrplay
./install_lib.sh
cd ..
rm -rf sdrplay
rm $BINARY

git clone https://github.com/SDRplay/SoapySDRPlay.git
cmakebuild SoapySDRPlay 1c2728a04db5edf8154d02f5cca87e655152d7c1

SUDO_FORCE_REMOVE=yes apt-get -y purge --autoremove $BUILD_PACKAGES
apt-get clean
rm -rf /var/lib/apt/lists/*
