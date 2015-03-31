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

"""
Version-controlled shared config for IPython Notebook.

Shared settings specified here are normally imported in the
non-version-controlled file ipython_notebook_config.py where you can
override settings on a site-specific basis.
"""

from django.conf import settings

# pylint: disable=E0602

c = get_config()
c.NotebookManager.notebook_dir = settings.PROJ_ROOT + 'data/notebook/'
c.IPKernelApp.pylab = 'inline'

#c.NotebookApp.base_url = '/notebook/'
#c.NotebookApp.base_project_url = '/notebook/'
#c.NotebookApp.base_kernel_url = '/notebook/'
