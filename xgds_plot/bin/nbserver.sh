#!/bin/bash
#__BEGIN_LICENSE__
# Copyright (c) 2015, United States Government, as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All rights reserved.
#
# The xGDS platform is licensed under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0.
#
# Unless required by applicable law or agreed to in writing, software distributed
# under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
# CONDITIONS OF ANY KIND, either express or implied. See the License for the
# specific language governing permissions and limitations under the License.
#__END_LICENSE__

# This script is intended to be run by /etc/init.d/nbserver at boot.
# An example version of the nbserver script can be found in version
# control in this directory.

if [ -d /home/irg ]; then
    EXEC_USER=irg
else
    EXEC_USER=vagrant
fi

THISDIR="$( cd "$( dirname "$0" )" && pwd )"
PROJ_ROOT=$(readlink -f "$THISDIR/../../../..")
NOTEBOOK_CONFIG_DIR=$PROJ_ROOT/var/notebook
JUPYTER_CONFIG_DIR=$NOTEBOOK_CONFIG_DIR/jupyter
IPYTHONDIR=$NOTEBOOK_CONFIG_DIR/ipython

PID_DIR=$JUPYTER_CONFIG_DIR/pid
if [ ! -d $PID_DIR ]; then
    mkdir -p $PID_DIR
fi
NBSERVER_PID_FILE=$PID_DIR/nbserver.pid

LOG_DIR=$JUPYTER_CONFIG_DIR/log
if [ ! -d $LOG_DIR ]; then
    mkdir -p $LOG_DIR
fi
NBSERVER_LOG_FILE=$LOG_DIR/nbserver.log

cd /

sudo -u $EXEC_USER -H bash <<EOF

source $PROJ_ROOT/sourceme.sh
echo >> $NBSERVER_LOG_FILE
echo >> $NBSERVER_LOG_FILE
echo _________________________________________________________ >> $NBSERVER_LOG_FILE
date >> $NBSERVER_LOG_FILE
echo "starting new notebook session" >> $NBSERVER_LOG_FILE

echo IPYTHONDIR=$IPYTHONDIR JUPYTER_CONFIG_DIR=$JUPYTER_CONFIG_DIR nohup jupyter notebook >> $NBSERVER_LOG_FILE
IPYTHONDIR=$IPYTHONDIR JUPYTER_CONFIG_DIR=$JUPYTER_CONFIG_DIR nohup jupyter notebook >> $NBSERVER_LOG_FILE 2>&1 &

echo \$! > $NBSERVER_PID_FILE

EOF
