#!/usr/bin/env bash
set -euo pipefail
export MAKEFLAGS="-j4"

cd /tmp

STATIC_PACKAGES="libusb-1.0-0 libatomic1"
BUILD_PACKAGES="git libusb-1.0-0-dev cmake make gcc g++"

apt-get update
apt-get -y install --no-install-recommends $STATIC_PACKAGES $BUILD_PACKAGES

SIMD_FLAGS=""
if [[ 'x86_64' == `uname -m` ]] ; then
    SIMD_FLAGS="-DDEFAULT_SIMD_FLAGS=SSE3"
fi

git clone https://github.com/myriadrf/LimeSuite.git
cd LimeSuite
git checkout 0854a51ec06b30b01f19a562149c39461e92f24d
mkdir builddir
cd builddir
cmake .. -DENABLE_EXAMPLES=OFF -DENABLE_DESKTOP=OFF -DENABLE_LIME_UTIL=OFF -DENABLE_QUICKTEST=OFF -DENABLE_OCTAVE=OFF -DENABLE_GUI=OFF -DCMAKE_CXX_STANDARD_LIBRARIES="-latomic" ${SIMD_FLAGS}
make
make install
cd ../..
rm -rf LimeSuite

apt-get -y purge --autoremove $BUILD_PACKAGES
apt-get clean
rm -rf /var/lib/apt/lists/*
