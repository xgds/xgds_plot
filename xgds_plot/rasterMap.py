# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

import os
import math
import sys
import shutil

import numpy
from scipy.ndimage import filters
from scipy.misc import pilutil
import matplotlib
matplotlib.use('Agg')  # non-interactive png plotting backend
from matplotlib import pyplot, mpl
import matplotlib.cm
from PIL import Image

from geocamUtil.store import FileStore, LruCacheStore
from geocamUtil.zmq.subscriber import ZmqSubscriber
from geocamUtil.zmq.delayBox import DelayBox

from xgds_plot.tile import getTilesOverlappingBounds, getPixelOfLonLat
from xgds_plot import settings
from xgds_plot.meta import TIME_SERIES_LOOKUP

MAX_TILES_IN_MEMORY = 100
N = settings.XGDS_PLOT_MAP_PIXELS_PER_TILE
DATA_PATH = os.path.join(settings.DATA_DIR,
                         settings.XGDS_PLOT_DATA_SUBDIR,
                         'map')

def getClassByName(qualifiedName):
    """
    converts 'moduleName.ClassName' to a class object
    """
    dotPos = qualifiedName.rindex('.')
    moduleName = qualifiedName[:dotPos]
    className = qualifiedName[(dotPos + 1):]
    __import__(moduleName)
    mod = sys.modules[moduleName]
    return getattr(mod, className)


class RasterListener(object):
    cacheSubdir = 'rasterListener'

    def __init__(self, layerIds, opts):
        self.layerIds = layerIds
        self.opts = opts

        self.cacheDir = os.path.join(DATA_PATH,
                                     'cache',
                                     self.cacheSubdir)
        self.delayBox = DelayBox(self.writeImages,
                                 maxDelaySeconds=1,
                                 numBuckets=10)
        self.tileUpdateCount = 0
        self.lon = None
        self.lat = None

        self.layers = []
        for layerId in self.layerIds:
            layerOpts = TIME_SERIES_LOOKUP[layerId]
            layerClass = getClassByName(layerOpts['map']['type'])
            layer = layerClass(self, layerId, layerOpts)
            self.layers.append(layer)

        self.subscriber = ZmqSubscriber(**ZmqSubscriber.getOptionValues(self.opts))

    def start(self):
        self.store = LruCacheStore(FileStore(self.cacheDir),
                                   MAX_TILES_IN_MEMORY)
        self.subscriber.start()
        self.delayBox.start()

    def stop(self):
        print '%s: syncing to disk' % self.__class__.__name__
        self.store.sync()
        self.delayBox.stop()

    @staticmethod
    def rmIfPossible(path):
        print '  deleting %s' % path
        try:
            shutil.rmtree(path)
        except OSError, oe:
            print >> sys.stderr, 'Failed to remove %s: %s' % (path, oe)

    @staticmethod
    def clean():
        RasterListener.rmIfPossible(DATA_PATH)

    @classmethod
    def getEmptyArrayBlock(cls, n):
        "Implement in subclasses."
        pass

    @classmethod
    def getTileKey(cls, tile):
        level, x, y = tile
        return '%s_%s_%s' % (level, x, y)

    @classmethod
    def spread(cls, M, sigma):
        return (2 * math.pi * sigma ** 2
                * filters.gaussian_filter(M, sigma))

    def writeImages(self, tile):
        tileKey = self.getTileKey(tile)
        tileData = self.store[tileKey]
        processedTileData = self.getProcessedTileData(tile, tileData)
        for layer in self.layers:
            layer.writeImage(tile, processedTileData)

    def getProcessedTileData(self, tile, tileData):
        """
        Subclasses can use this function to pre-process a tile before
        handing it off to a RasterMap for output. It returns a
        processedTileData object in whatever format the RasterMap's
        writeImage() method expects.
        """
        return tileData

    def writeToTile(self, rec, tile):
        level, _x, _y = tile
        _x, _y, i, j = getPixelOfLonLat(level, self.lon, self.lat)
        if 0 <= i < N and 0 <= j < N:
            tileKey = self.getTileKey(tile)
            try:
                tileData = self.store[tileKey]
            except KeyError:
                tileData = self.getEmptyArrayBlock(N)
            self.writeTileData(rec, tileData, i, j)
            self.store[tileKey] = tileData

    def writeTileData(self, rec, tileData, i, j):
        "Implement in subclasses."
        pass

    def handleTileUpdate(self, topic, msg):
        if self.lon is None:
            print 'got instrument data before first position update'
            return
        for tile in getTilesOverlappingBounds((self.lon, self.lat,
                                               self.lon, self.lat)):
            rec = msg['data']['fields']
            self.writeToTile(rec, tile)
            self.delayBox.addJob(tile)
        self.tileUpdateCount += 1
        if self.tileUpdateCount % 100 == 0:
            print '%d tile update' % self.tileUpdateCount


class RasterMap(object):
    def __init__(self, collector, layerId, opts):
        self.collector = collector
        self.layerId = layerId
        self.opts = opts

        self.name = self.opts['valueName']
        self.colorRange = self.opts['map']['colorRange']

        self.mapDir = os.path.join(DATA_PATH,
                                   self.layerId)
        self.rgba = numpy.zeros((N, N, 4), dtype='uint8')

        colorBarPath = os.path.join(DATA_PATH,
                                    self.layerId,
                                    'colorbar.png')
        self.writeColorBar(colorBarPath)

    @classmethod
    def scaleAndClip(cls, M, crange):
        cmin, cmax = crange
        M = (M - cmin) / (cmax - cmin)
        M = numpy.maximum(0.0, M)
        M = numpy.minimum(1.0, M)
        return M

    def writeImage(self, tile, processedTileData):
        im = self.getImage(tile, processedTileData)

        level, x, y = tile
        outPath = '%s/%d/%d/%d.png' % (self.mapDir, level, x, y)
        outDir = os.path.dirname(outPath)
        if not os.path.exists(outDir):
            os.makedirs(outDir)
        im.save(outPath)

    def getImageArray(self, processedTileData):
        """
        Implement in subclasses. Returns (signal, alpha). Both should be
        floating-point arrays. Signal is mapped to a color using
        self.colorRange. Alpha values should be in the range [0, 1].
        """
        pass

    def getImage(self, tile, processedTileData):
        signal, alpha = self.getImageArray(processedTileData)

        signal = self.scaleAndClip(signal, self.colorRange)

        rgba = self.rgba
        rgba = matplotlib.cm.jet(signal, bytes=True)  # pylint: disable=E1101
        rgba[:, :, 3] = pilutil.bytescale(alpha, cmin=0.0, cmax=1.0)
        rgbaT = rgba.transpose((1, 0, 2)).copy()
        return Image.frombuffer('RGBA', (N, N), rgbaT,
                                'raw', 'RGBA', 0, 1)

    def writeColorBar(self, path):
        if os.path.exists(path):
            return

        fig = pyplot.figure(figsize=(4, 0.7), dpi=100)
        ax = fig.add_axes([0.05, 0.6, 0.9, 0.3])

        cmap = mpl.cm.jet  # pylint: disable=E1101
        vmin, vmax = self.colorRange
        norm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)

        cb = mpl.colorbar.ColorbarBase(ax, cmap=cmap,
                                       norm=norm,
                                       orientation='horizontal')
        cb.set_label(self.name)

        outDir = os.path.dirname(os.path.realpath(path))
        if not os.path.exists(outDir):
            os.makedirs(outDir)
        pyplot.savefig(path)
