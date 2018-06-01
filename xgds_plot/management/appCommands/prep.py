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
This is a place to put any prep code you need to run before your app
is ready.

For example, you might need to render some icons.  The convention for
that is to put the source data in your app's media_src directory and
render the icons into your app's build/media directory (outside version
control).

How this script gets run: when the site admin runs "./manage.py prep",
one of the steps is "prepapps", which calls
management/appCommands/prep.py command for each app (if it exists).
"""

import os
import shutil

from django.core.management.base import BaseCommand

from geocamUtil.Builder import Builder
from geocamUtil.Installer import Installer

from django.conf import settings


class Command(BaseCommand):
    help = 'Prep xgds_plot'

    def handle(self, *args, **options):
        if False:
            # TODO right now this throws the error from GEOCAM_UTIL_INSTALLER_USE_SYMLINKS being false
            _d = os.path.dirname
            appDir = _d(_d(_d(os.path.abspath(__file__))))

            b = Builder()
            self.generateNotebookDir(b, appDir)
            b.finish()

    def generateNotebookDir(self, builder, appDir):
        assert settings.GEOCAM_UTIL_INSTALLER_USE_SYMLINKS, \
            'generateNotebookDir: very error-prone if not using symlinks'
        notebookDir = os.path.join(appDir, 'notebook')

        jupyterDir = os.path.join(notebookDir, 'jupyter')
        if not os.path.exists(jupyterDir):
            os.makedirs(jupyterDir)

        ipythonDir = os.path.join(notebookDir, 'ipython')
        ipythonProfileDir = os.path.join(ipythonDir, 'profile_default')
        if not os.path.exists(ipythonProfileDir):
            os.makedirs(ipythonProfileDir)

        # generate initial non-shared config files if not already present
        jupyterConfig = os.path.join(jupyterDir, 'jupyter_notebook_config.py')
        if not os.path.exists(jupyterConfig):
            jupyterConfigTemplate = os.path.join(appDir, 'management', 'templates',
                                                 'jupyter_notebook_config.py')
            shutil.copyfile(jupyterConfigTemplate, jupyterConfig)
        ipythonConfig = os.path.join(ipythonProfileDir, 'ipython_config.py')
        if not os.path.exists(ipythonConfig):
            ipythonConfigTemplate = os.path.join(appDir, 'management', 'templates',
                                                 'ipython_config.py')
            shutil.copyfile(ipythonConfigTemplate, ipythonConfig)

        # symlink the contents of the notebook directory under the <site>/var directory
        installer = Installer(builder)
        varNotebookDir = os.path.join(settings.VAR_ROOT, 'notebook')
        installer.installRecurse(notebookDir, varNotebookDir)

        # make the directory to hold notebook files, if it doesn't already exist
        dataDir = os.path.join(settings.DATA_ROOT, 'notebook')
        if not os.path.exists(dataDir):
            os.makedirs(dataDir)

        # symlink extra startup files (these files will be site-specific, not part of
        # the xgds_plot app)
        startupDir = os.path.join(varNotebookDir, 'ipython', 'profile_default',
                                  'startup')
        for f in settings.XGDS_PLOT_NOTEBOOK_STARTUP_FILES:
            installer.installFile(f, startupDir)
