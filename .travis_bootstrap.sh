#!/bin/bash

apt-get update -qq
apt-get install -y make flex bison libtool libevent-dev automake pkg-config libssl-dev libboost-all-dev libbz2-dev build-essential g++ python-dev git
git clone https://github.com/apache/thrift.git

pushd thrift/
    git checkout 0.9.1
    ./bootstrap.sh
    ./configure --with-boost-filesystem=boost_filesystem --with-boost-libdir=/usr/lib/x86_64-linux-gnu --with-cpp=yes --with-python=yes --with-py3=yes --with-d=no --with-java=no --with-ruby=no --with-haskell=no --with-rs=no --with-go=no --with-nodejs=no --with-dart=no --with-lua=no --with-php=no --with-csharp=no --with-erlang=no --with-perl=no --with-dotnetcore=no --with-haxe=no
    make
    make install

    pushd contrib/fb303/
        ./bootstrap.sh
        make
        make install
    popd
popd

git clone git://github.com/facebook/scribe.git

pushd scribe/
    # https://github.com/facebookarchive/scribe/pull/83
    sed -i 's/^AM_INIT_AUTOMAKE/# AM_INIT_AUTOMAKE/g' configure.ac
    sed -i 's/EXTERNAL_LIBS += /EXTERNAL_LIBS += $(BOOST_SYSTEM_LIB) $(BOOST_FILESYSTEM_LIB) /g' src/Makefile.am
    ./bootstrap.sh --with-boost-system=boost_system --with-boost-filesystem=boost_filesystem
    make
    make install
popd
