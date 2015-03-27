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

import os
import math
import sys

import numpy
from scipy.ndimage import filters

from xgds_plot import settings

# pylint: disable=E1101

EARTH_RADIUS_METERS = 6371 * 1000
METERS_PER_DEGREE = 2 * math.pi * EARTH_RADIUS_METERS / 360
DATA_PATH = os.path.join(settings.DATA_ROOT,
                         settings.XGDS_PLOT_DATA_SUBDIR,
                         'map')

N = settings.XGDS_PLOT_MAP_PIXELS_PER_TILE


def dosys(cmd):
    ret = os.system(cmd)
    if ret != 0:
        print >> sys.stderr, 'warning: command exited with non-zero return value %d' % ret
        print >> sys.stderr, '  command was: %s' % cmd
    return ret


def getTileBounds(level, x, y):
    tileSize = 360.0 / 2 ** level
    west = -180 + x * tileSize
    south = -90 + y * tileSize
    east = west + tileSize
    north = south + tileSize
    return west, south, east, north


def getTileContainingPoint(level, lon, lat):
    tileSize = 360.0 / 2 ** level
    x = int((lon - (-180) + settings.XGDS_PLOT_MAP_TILE_EPS) / tileSize)
    y = int((lat - (-90) + settings.XGDS_PLOT_MAP_TILE_EPS) / tileSize)
    return x, y


def getPixelOfLonLat(level, lon, lat):
    tileSize = 360.0 / 2 ** level
    xf = (lon - (-180) + settings.XGDS_PLOT_MAP_TILE_EPS) / tileSize
    x = int(xf)
    i = int(settings.XGDS_PLOT_MAP_PIXELS_PER_TILE * (xf - x))
    yf = (lat - (-90) + settings.XGDS_PLOT_MAP_TILE_EPS) / tileSize
    y = int(yf)
    j = int(settings.XGDS_PLOT_MAP_PIXELS_PER_TILE * (1.0 - (yf - y)))
    return x, y, i, j


def getTileContainingBounds(bounds):
    west, south, east, north = bounds
    diam = max(east - west, south - north) - settings.XGDS_PLOT_MAP_TILE_EPS
    level = int(math.floor(math.log(360.0 / diam, 2)))
    while 1:
        x, y = getTileContainingPoint(level, west, south)
        _tileWest, _tileSouth, tileEast, tileNorth = getTileBounds(level, x, y)
        if (east <= tileEast + settings.XGDS_PLOT_MAP_TILE_EPS and
                north <= tileNorth + settings.XGDS_PLOT_MAP_TILE_EPS):
            break
        level -= 1
    return level, x, y


def getTilesOverlappingBounds(dayCode, bounds, levels=None):
    zoomMin, zoomMax = settings.XGDS_PLOT_MAP_ZOOM_RANGE
    if levels is None:
        levels = xrange(zoomMin, zoomMax)
    west, south, east, north = bounds
    for level in levels:
        xmin, ymin = getTileContainingPoint(level, west, south)
        xmax, ymax = getTileContainingPoint(level, east, north)
        for x in xrange(xmin, xmax + 1):
            for y in xrange(ymin, ymax + 1):
                yield dayCode, level, x, y


def getLatLonBox(bounds):
    return ("""
<LatLonBox>
  <west>%s</west>
  <south>%s</south>
  <east>%s</east>
  <north>%s</north>
</LatLonBox>
""" % bounds)


def getLatLonAltBox(bounds):
    return ("""
<LatLonAltBox>
  <west>%s</west>
  <south>%s</south>
  <east>%s</east>
  <north>%s</north>
</LatLonAltBox>
""" % bounds)


def getMetersPerPixel(level):
    radiansPerTile = 2 * math.pi / 2 ** level
    metersPerTile = radiansPerTile * EARTH_RADIUS_METERS
    return metersPerTile / settings.XGDS_PLOT_MAP_PIXELS_PER_TILE


class ScalarTile(object):
    @classmethod
    def spread(cls, M, sigma):
        return (2 * math.pi * sigma ** 2
                * filters.gaussian_filter(M, sigma))

    def __init__(self, tileParams, smoothingMeters, opaqueWeight):
        self.tileParams = tileParams
        self.smoothingMeters = smoothingMeters
        self.opaqueWeight = opaqueWeight

        # even when zoomed all the way out, do minimal blurring of
        # 0.5 pixels to make data more visible
        _dayCode, level, _x, _y = self.tileParams
        self.sigmaPixels = max(0.5, self.smoothingMeters / getMetersPerPixel(level))

        self.numSum = numpy.zeros((N, N))
        self.weightSum = numpy.zeros((N, N))

    def addSample(self, val, i, j):
        self.numSum[i, j] += val
        self.weightSum[i, j] += 1

    def getSmoothed(self):
        sumBlurred = filters.gaussian_filter(self.numSum, self.sigmaPixels)
        weightSumBlurred = filters.gaussian_filter(self.weightSum, self.sigmaPixels)

        alpha = self.spread(self.weightSum / self.opaqueWeight,
                            self.sigmaPixels)
        alpha[alpha < 0.1] = 0
        alpha[alpha > 1.0] = 1

        result = sumBlurred / (weightSumBlurred + 1e-3)
        result[alpha < 0.1] = 0

        return result, alpha


class RatioTile(ScalarTile):
    def __init__(self, tileParams, smoothingMeters, opaqueWeight):
        super(RatioTile, self).__init__(tileParams, smoothingMeters, opaqueWeight)

        self.denomSum = numpy.zeros((N, N))

    def addSample(self, vals, i, j):
        num, denom = vals
        self.numSum[i, j] += num
        self.denomSum[i, j] += denom
        self.weightSum[i, j] += 1

    def getSmoothed(self):
        numSumBlurred = filters.gaussian_filter(self.numSum, self.sigmaPixels)

        alpha = self.spread(self.weightSum / self.opaqueWeight,
                            self.sigmaPixels)
        alpha[alpha < 0.1] = 0
        alpha[alpha > 1.0] = 1

        denomSumBlurred = filters.gaussian_filter(self.denomSum, self.sigmaPixels)
        denomSumBlurred[alpha < 0.1] = 1  # avoid divide by zero

        result = numSumBlurred / (denomSumBlurred + 1e-20)
        result[alpha < 0.1] = 0

        return result, alpha
