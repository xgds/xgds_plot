# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
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
import logging
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

        # generate initial ipython_notebook_config.py file if not already present
        if not os.path.exists(siteConfig):
            siteConfigTemplate = os.path.join(appDir, 'management', 'templates',
                                              'ipython_notebook_config.py')
            shutil.copyfile(siteConfigTemplate, siteConfig)

        # symlink the contents of the notebook directory under the <site>/var directory
        installer = Installer(builder)
        installProfileDir = os.path.join(settings.VAR_ROOT, 'notebook', 'profile_default')
        installer.installRecurse(profileDir, installProfileDir)

        # symlink extra startup files
        startupDir = os.path.join(installProfileDir, 'startup')
        for f in settings.XGDS_PLOT_NOTEBOOK_STARTUP_FILES:
            installer.installFile(f, startupDir)
