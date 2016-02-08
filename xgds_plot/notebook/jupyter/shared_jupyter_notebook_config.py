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
shared_jupyter_notebook_config.py is where you put customizations for the
Jupyter notebook that you want to share across all sites that use the
xgds_plot app. If you want to do customizations for a particular
deployment, use jupyter_notebook_config.py instead.
"""

from django.conf import settings

# pylint: disable=E0602

c = get_config()

# Don't try to open a local browser on launch. (We run the notebook server
# as a daemon on a headless server and expect remote users to connect.)
c.NotebookApp.open_browser = False

# Put the precious notebook files themselves in a subdirectory of the site's
# 'data' folder. The 'var' folder where most of the config information lives
# is considered non-precious -- it contains symlinks to version-controlled
# files and non-precious error logs and pid files.
c.NotebookApp.notebook_dir = settings.PROJ_ROOT + 'data/notebook/'

# Put the notebook server at the '/notebook' path. This is required
# for the way we use the Apache server as a proxy. The tornado_settings
# path change is trying to make sure requests for static files like
# icons used by the Jupyter notebook are also routed to the Jupyter
# server, so they load properly.
c.NotebookApp.base_url = '/notebook'
c.NotebookApp.tornado_settings = {'static_url_prefix': '/notebook/static/'}
