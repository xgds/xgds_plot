
Jupyter uses a configuration directory called $JUPYTER_CONFIG_DIR to store its
settings. $JUPYTER_CONFIG_DIR is normally set to ~/.jupyter/.

We set $JUPYTER_CONFIG_DIR to the <site>/var/notebook/jupyter directory
instead, because we don't want to hide xGDS files in dot-directories
and distribute them throughout the file system.

Some of the files in $JUPYTER_CONFIG_DIR are manually edited and precious;
others (log files, pid files, etc.) are non-precious. We keep the
original precious files in this version-controlled directory, and
symlink to them from <site>/var/notebook/jupyter. This allows
<site>/var to be removed and rebuilt at any time, and avoids dropping
temp files inside a version-controlled directory.

.. o __BEGIN_LICENSE__
.. o  Copyright (c) 2015, United States Government, as represented by the
.. o  Administrator of the National Aeronautics and Space Administration.
.. o  All rights reserved.
.. o
.. o  The xGDS platform is licensed under the Apache License, Version 2.0
.. o  (the "License"); you may not use this file except in compliance with the License.
.. o  You may obtain a copy of the License at
.. o  http://www.apache.org/licenses/LICENSE-2.0.
.. o
.. o  Unless required by applicable law or agreed to in writing, software distributed
.. o  under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
.. o  CONDITIONS OF ANY KIND, either express or implied. See the License for the
.. o  specific language governing permissions and limitations under the License.
.. o __END_LICENSE__
