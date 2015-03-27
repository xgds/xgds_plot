# __BEGIN_LICENSE__
#Copyright © 2015, United States Government, as represented by the 
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

from django.core.management.base import NoArgsCommand

from geocamUtil.Builder import Builder
from geocamUtil.Installer import Installer
from geocamUtil import settings as geocamUtilSettings

from xgds_plot import settings


class Command(NoArgsCommand):
    help = 'Prep xgds_plot'

    def handle_noargs(self, **options):
        _d = os.path.dirname
        appDir = _d(_d(_d(os.path.abspath(__file__))))

        b = Builder()
        self.generateNotebookDir(b, appDir)
        b.finish()

    def generateNotebookDir(self, builder, appDir):
        assert geocamUtilSettings.GEOCAM_UTIL_INSTALLER_USE_SYMLINKS, \
            'generateNotebookDir: very error-prone if not using symlinks'
        profileDir = os.path.join(appDir, 'notebook', 'profile_default')
        siteConfig = os.path.join(profileDir, 'ipython_notebook_config.py')

        if not os.path.exists(profileDir):
            os.makedirs(profileDir)

        # generate initial ipython_notebook_config.py file if not already present
        if not os.path.exists(siteConfig):
            siteConfigTemplate = os.path.join(appDir, 'management', 'templates',
                                              'ipython_notebook_config.py')
            shutil.copyfile(siteConfigTemplate, siteConfig)

        # symlink the contents of the notebook directory under the <site>/var directory
        installer = Installer(builder)
        installProfileDir = os.path.join(settings.VAR_ROOT, 'notebook', 'profile_default')
        installer.installRecurse(profileDir, installProfileDir)
        installer.installRecurse(os.path.join(appDir, 'notebook', 'nbextensions'),
                                 os.path.join(settings.VAR_ROOT, 'notebook', 'nbextensions'))

        dataDir = os.path.join(settings.DATA_ROOT, 'notebook')
        if not os.path.exists(dataDir):
            os.makedirs(dataDir)

        # symlink extra startup files
        startupDir = os.path.join(installProfileDir, 'startup')
        for f in settings.XGDS_PLOT_NOTEBOOK_STARTUP_FILES:
            installer.installFile(f, startupDir)
