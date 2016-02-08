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

"""
shared_ipython_config.py is where you put customizations for IPython kernels
that you want to share across all sites that use the xgds_plot app. If you want
to do customizations for a particular deployment, use ipython_config.py instead.

More info at http://ipython.readthedocs.org/en/stable/config/intro.html
"""

# Pre-load matplotlib and numpy for interactive use, selecting a particular
# matplotlib backend and loop integration.
c.InteractiveShellApp.pylab = 'inline'
