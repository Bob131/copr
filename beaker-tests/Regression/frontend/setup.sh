#!/bin/bash

export SCRIPTPATH="$( builtin cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export LANG=en_US.utf8

# primarily install git for the setup below
dnf -y install git

if [[ `pwd` =~ ^/mnt/tests.*$ ]]; then
    echo "Setting up native beaker environment."
    git clone https://pagure.io/copr/copr.git
    export COPRROOTDIR=$SCRIPTPATH/copr
else
    echo "Setting up from source tree."
    export COPRROOTDIR=$SCRIPTPATH/../../../
fi

# install files from 'files'
#cp -rT $SCRIPTPATH/files /

# install stuff needed for the test
dnf -y install vagrant
dnf -y install vagrant-libvirt
dnf -y install jq
dnf -y install tito

# enable libvirtd for Vagrant (distgit)
systemctl enable libvirtd && systemctl start libvirtd

# setup dist-git & copr-dist-git
tar -C $SCRIPTPATH/frontend-files -cf $COPRROOTDIR/frontend-files.tar .
cd $COPRROOTDIR
vagrant up frontend
vagrant ssh -c '
sudo tar -xf /vagrant/frontend-files.tar -C /
echo "*:*:coprdb:copr-fe:coprpass" > ~/.pgpass
chmod 600 ~/.pgpass
psql -U copr-fe coprdb < /setup-user.sql
sudo copr-frontend create_chroot fedora-24-x86_64
' frontend
rm $COPRROOTDIR/frontend-files.tar
