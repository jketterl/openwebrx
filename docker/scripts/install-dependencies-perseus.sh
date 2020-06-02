#!/usr/bin/env bash
set -euxo pipefail
export MAKEFLAGS="-j4"

cd /tmp

STATIC_PACKAGES="libusb-1.0-0 libudev1"
BUILD_PACKAGES="git make gcc autoconf automake libtool libusb-1.0-0-dev xxd"

apt-get update
apt-get -y install --no-install-recommends $STATIC_PACKAGES $BUILD_PACKAGES

git clone https://github.com/Microtelecom/libperseus-sdr.git
cd libperseus-sdr
git checkout 72ac67c5b7936a1991be0ec97c03a59c1a8ac8f3
./bootstrap.sh
./configure
make
make install
ldconfig /etc/ld.so.conf.d
cd ..
rm -rf libperseus-sdr

apt-get -y purge --autoremove $BUILD_PACKAGES
apt-get clean
rm -rf /var/lib/apt/lists/*
