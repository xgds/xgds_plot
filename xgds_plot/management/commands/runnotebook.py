# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

"""
Runs the IPython Notebook with settings linked to this xGDS installation.
"""

import os
import logging

from django.core.management.base import NoArgsCommand

from xgds_plot import settings


def dosys(cmd):
    logging.info(cmd)
    ret = os.system(cmd)
    if ret != 0:
        logging.warning('command exited with non-zero return value %s', ret)
    return ret


class Command(NoArgsCommand):
    help = 'Prep isruApp'

    def handle_noargs(self, **options):
        if 'IPYTHONDIR' not in os.environ:
            os.environ['IPYTHONDIR'] = settings.VAR_ROOT + 'notebook/'
        dosys('ipython notebook --no-browser')
