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

import collections

from django.test import TestCase

from xgds_plot.tile import getTileBounds, getTileContainingPoint, getTileContainingBounds
from xgds_plot import settings


class TileTest(TestCase):
    def assertNearlyEqual(self, a, b, msg=None, delta=settings.XGDS_PLOT_MAP_TILE_EPS):
        if isinstance(a, collections.Iterable):
            for ai, bi in zip(a, b):
                if abs(ai - bi) > delta:
                    if not msg:
                        msg = '%s != %s within %g delta' % (a, b, delta)
                    raise AssertionError(msg)
        else:
            super(TileTest, self).assertNearlyEqual(a, b, msg=msg, delta=delta)

    def test_getTileBounds(self):
        self.assertNearlyEqual(getTileBounds(level=1, x=0, y=0),
                               (-180, -90, 0, 90))
        self.assertNearlyEqual(getTileBounds(level=1, x=1, y=0),
                               (0, -90, 180, 90))
        self.assertNearlyEqual(getTileBounds(level=3, x=2, y=2),
                               (-90, 0, -45, 45))

    def test_getTileContainingPoint(self):
        self.assertEqual(getTileContainingPoint(level=1, lon=-160, lat=-45),
                         (0, 0))
        self.assertEqual(getTileContainingPoint(level=3, lon=-120, lat=-30),
                         (1, 1))

    def test_getTileContainingBounds(self):
        self.assertEqual(getTileContainingBounds([-179, -89, -1, 89]),
                         (1, 0, 0))
        self.assertEqual(getTileContainingBounds([-134, -44, -91, -1]),
                         (3, 1, 1))
        self.assertEqual(getTileContainingBounds([-134, -44, -89, -1]),
                         (1, 0, 0))
