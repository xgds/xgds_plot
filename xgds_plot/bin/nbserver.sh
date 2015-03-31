#!/bin/bash
# __BEGIN_LICENSE__
#Copyright (c) 2015, United States Government, as represented by the 
#Administrator of the National Aeronautics and Space Administration. 
#All rights reserved.
#
#The xGDS platform is licensed under the Apache License, Version 2.0 
#(the "License"); you may not use this file except in compliance with the License. 
#You may obtain a copy of the License at 
#http://www.apache.org/licenses/LICENSE-2.0.
#
#Unless required by applicable law or agreed to in writing, software distributed 
#under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR 
#CONDITIONS OF ANY KIND, either express or implied. See the License for the 
#specific language governing permissions and limitations under the License.
# __END_LICENSE__

# This script is intended to be run by /etc/init.d/nbserver at boot.
# An example version of the nbserver script can be found in version
# control in this directory.

THISDIR="$( cd "$( dirname "$0" )" && pwd )"
PROJ_ROOT="$THISDIR/../../../.."
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
