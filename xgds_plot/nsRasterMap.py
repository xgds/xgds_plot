# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

import os

import numpy
from scipy.ndimage import filters

from geocamUtil.geomath import transformEnuToLonLatAlt
from geocamUtil import KmlUtil

from xgds_plot.tile import getMetersPerPixel
from xgds_plot.rasterMap import RasterListener, RasterMap
from xgds_plot import settings
from xgds_plot import meta

from isruApp.PoseConvert import headingFromYaw

N = settings.XGDS_PLOT_MAP_PIXELS_PER_TILE
DATA_PATH = os.path.join(settings.DATA_DIR,
                         settings.XGDS_PLOT_DATA_SUBDIR,
                         'map')

REFERENCE_META = meta.TIME_SERIES_LOOKUP['snScalar']
BLUR_METERS = REFERENCE_META['map']['smoothingMeters']
OPAQUE_WEIGHT = REFERENCE_META['map']['opaqueWeight']


def writePlacemark(path, lon, lat, heading):
    outDir = os.path.dirname(path)
    if not os.path.exists(outDir):
        os.makedirs(outDir)

    pathTmp = '%s.part' % path
    out = file(pathTmp, 'w')
    out.write(KmlUtil.wrapKml("""
<Placemark>
  <Point>
    <coordinates>%(lon)s,%(lat)s</coordinates>
  </Point>
  <Style>
    <IconStyle>
      <Icon>
        <href>http://10.10.80.80/xgds_isru/static/isruApp/icons/artemis.png</href>
      </Icon>
      <heading>%(heading)s</heading>
    </IconStyle>
  </Style>
</Placemark>
""" % dict(lon=lon, lat=lat, heading=heading)))
    out.close()
    os.rename(pathTmp, path)


class DotDict(object):
    def __init__(self, **kwargs):
        for k, v in kwargs.iteritems():
            setattr(self, k, v)


class NsListener(RasterListener):
    cacheSubdir = 'ns'

    def __init__(self, layerIds, opts):
        super(NsListener, self).__init__(layerIds, opts)
        self.poseCount = 0

    def start(self):
        super(NsListener, self).start()
        self.subscriber.subscribeJson('isruApp.ddsnstier1data:', self.handleTileUpdate)
        self.subscriber.subscribeJson('isruApp_pastassetposition:', self.handlePose)

    @classmethod
    def getEmptyArrayBlock(cls, n):
        return {'snsSum': numpy.zeros((n, n)),
                'cdsSum': numpy.zeros((n, n)),
                'weightSum': numpy.zeros((n, n))}

    def writeTileData(self, rec, tileData, i, j):
        tileData['weightSum'][i, j] += 1
        tileData['snsSum'][i, j] += rec['snScalar']
        tileData['cdsSum'][i, j] += rec['cdScalar']

    def getProcessedTileData(self, tile, tileData):
        weightSum = tileData['weightSum']
        snsSum = tileData['snsSum']
        cdsSum = tileData['cdsSum']

        # even when zoomed all the way out, do minimal blurring of
        # 0.5 pixels to make data more visible
        level, _x, _y = tile
        sigmaPixels = max(0.5, BLUR_METERS / getMetersPerPixel(level))

        alpha = self.spread(weightSum / OPAQUE_WEIGHT,
                            sigmaPixels)
        alpha[alpha < 0.1] = 0
        alpha[alpha > 1.0] = 1

        cdsSumBlurred = filters.gaussian_filter(cdsSum, sigmaPixels)
        cdsSumBlurred[alpha < 0.1] = 1  # avoid divide by zero

        snsSumBlurred = filters.gaussian_filter(snsSum, sigmaPixels)

        weightSumBlurred = filters.gaussian_filter(weightSum, sigmaPixels)

        return DotDict(snsSumBlurred=snsSumBlurred,
                       cdsSumBlurred=cdsSumBlurred,
                       weightSumBlurred=weightSumBlurred,
                       alpha=alpha)

    def handlePose(self, topic, pos):
        self.lon = pos['longitude']
        self.lat = pos['latitude']
        self.heading = pos['heading']
        writePlacemark(os.path.join(settings.DATA_DIR,
                                    settings.ISRU_APP_DATA_SUBDIR,
                                    'roverCurrent.kml'),
                       self.lon, self.lat, self.heading)
        self.poseCount += 1
        if self.poseCount % 100 == 0:
            print '%d pose' % self.poseCount


class NsRatioMap(RasterMap):
    def getImageArray(self, d):
        # add epsilon to avoid divide-by-zero
        ratio = d.snsSumBlurred / (d.cdsSumBlurred + 1e-3)
        ratio[d.alpha < 0.1] = 0

        return ratio, d.alpha


class NsSnMap(RasterMap):
    def getImageArray(self, d):
        # add epsilon to avoid divide-by-zero
        sn = d.snsSumBlurred / (d.weightSumBlurred + 1e-3)
        sn[d.alpha < 0.1] = 0

        return sn, d.alpha
