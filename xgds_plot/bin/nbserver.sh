#!/bin/bash

# This script is intended to be run by /etc/init.d/nbserver at boot.
# An example version of the nbserver script can be found in version
# control in this directory.

PROJ_ROOT=/usr/local/irg/releases/xgds/xgds_isru
IPYTHONDIR=$PROJ_ROOT/var/notebook
NBSERVER_PID_FILE=$IPYTHONDIR/profile_default/pid/nbserver.pid
NBSERVER_LOG_FILE=$IPYTHONDIR/profile_default/log/nbserver.log
cd /

sudo -u irg -H bash <<EOF

source $PROJ_ROOT/sourceme.sh
echo >> $NBSERVER_LOG_FILE
echo >> $NBSERVER_LOG_FILE
date >> $NBSERVER_LOG_FILE
echo "starting new notebook session" >> $NBSERVER_LOG_FILE
echo ipython notebook --ipython-dir=$IPYTHONDIR --no-browser >> $NBSERVER_LOG_FILE 2>&1
nohup ipython notebook --ipython-dir=$IPYTHONDIR --no-browser >> $NBSERVER_LOG_FILE 2>&1 &
echo \$! > $NBSERVER_PID_FILE

EOF
