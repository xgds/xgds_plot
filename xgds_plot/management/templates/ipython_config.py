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
ipython_config.py is a place for you to put deployment-specific
custom settings for IPython kernels. These custom settings will not
be shared with other deployments. Settings made here override the shared
settings specified in shared_ipython_config.py.

This file must not be checked into version control!

More info at http://ipython.readthedocs.org/en/stable/config/intro.html
"""

# pylint: disable=E0602

# load shared settings from shared_ipython_config.py in this directory
load_subconfig('shared_ipython_config.py')

######################################################################
# Add your modifications below this point
