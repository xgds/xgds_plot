# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
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
