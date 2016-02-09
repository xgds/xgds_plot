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
Runs the IPython Notebook with settings linked to this xGDS installation.
"""

import os
import logging

from django.core.management.base import BaseCommand

from django.conf import settings


def dosys(cmd):
    logging.info(cmd)
    ret = os.system(cmd)
    if ret != 0:
        logging.warning('command exited with non-zero return value %s', ret)
    return ret


class Command(BaseCommand):
    help = 'Prep isruApp'

    def handle(self, *args, **options):
        if 'IPYTHONDIR' not in os.environ:
            os.environ['IPYTHONDIR'] = settings.VAR_ROOT + 'notebook/'
        dosys('ipython notebook --no-browser')
