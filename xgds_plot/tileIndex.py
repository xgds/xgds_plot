# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

import os
import sys
from collections import deque
import time

from django import db
import numpy
from scipy.ndimage import filters
from scipy.misc import pilutil
import matplotlib
matplotlib.use('Agg')  # non-interactive png plotting backend
from matplotlib import pyplot, mpl
import matplotlib.cm
from PIL import Image

from geocamUtil import anyjson as json
from geocamUtil.loader import getClassByName
from geocamUtil import TimeUtil

from xgds_plot import settings, tile, plotUtil

N = settings.XGDS_PLOT_MAP_PIXELS_PER_TILE

DATA_PATH = os.path.join(settings.DATA_DIR,
                         settings.XGDS_PLOT_DATA_SUBDIR,
                         'map')

BATCH_READ_NUM_SAMPLES = 5000
BATCH_SLEEP_NUM_SAMPLES = 100
BATCH_SLEEP_TIME_FACTOR = 3


class TileIndex(object):
    @classmethod
    def getTileKey(cls, valueCode, tile):
        level, x, y = tile
        return '%s_%s_%s_%s' % (valueCode, level, x, y)

    @classmethod
    def scaleAndClip(cls, M, crange):
        cmin, cmax = crange
        M = (M - cmin) / (cmax - cmin)
        M = numpy.maximum(0.0, M)
        M = numpy.minimum(1.0, M)
        return M

    def __init__(self, meta, parent, batchIndexAtStart=True):
        self.meta = meta
        self.parent = parent
        self.queueMode = batchIndexAtStart

        self.rgba = numpy.zeros((N, N, 4), dtype='uint8')

        queryClass = getClassByName(self.meta['queryType'])
        self.queryManager = queryClass(self.meta)

        self.valueClass = getClassByName(self.meta['valueType'])
        self.valueManager = self.valueClass(self.meta,
                                            self.queryManager)

        self.valueCode = self.meta['valueCode']
        self.outputDir = os.path.join(DATA_PATH,
                                      self.valueCode)

        self.colorRange = self.meta['map']['colorRange']
        colorBarPath = os.path.join(DATA_PATH,
                                    self.valueCode,
                                    'colorbar.png')
        self.writeColorBar(colorBarPath)

        self.queue = deque()
        self.running = False

    def start(self):
        self.queryManager.subscribeDjango(self.parent.subscriber,
                                          lambda topic, obj: self.handleRecord(obj))

        poseCollectorClass = getClassByName(self.meta['map']['poseCollector'])
        self.poseCollector = poseCollectorClass(self.parent.subscriber)

        self.running = True

        self.statusPath = os.path.join(self.outputDir,
                                       'status.json')
        self.statusStore = plotUtil.JsonStore(self.statusPath)
        self.status = self.statusStore.read(dflt={
            'minTime': None,
            'maxTime': None,
            'numSamples': 0,
            'numTiles': 0
        })

        self.batchProcessStartTime = time.time()
        if self.queueMode:
            self.batchIndex()

    def stop(self):
        if self.running:
            self.statusStore.write(self.status)
            self.running = False

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
        cb.set_label(self.meta['valueName'])

        outDir = os.path.dirname(os.path.realpath(path))
        if not os.path.exists(outDir):
            os.makedirs(outDir)
        pyplot.savefig(path)

    def handleRecord(self, obj):
        if self.queueMode:
            self.queue.append(obj)
        else:
            self.indexRecord(obj)

    def indexRecord(self, obj):
        if (self.status['numSamples'] % BATCH_SLEEP_NUM_SAMPLES) == 0:
            batchProcessDuration = time.time() - self.batchProcessStartTime
            sleepTime = batchProcessDuration * BATCH_SLEEP_TIME_FACTOR
            print 'sleeping for %.3f seconds to avoid overloading server' % sleepTime
            time.sleep(sleepTime)
            self.batchProcessStartTime = time.time()

        posixTimeMs = self.queryManager.getTimestamp(obj)
        maxTime = self.status['maxTime'] or -99e+20
        pos = self.poseCollector.getLastPositionBeforePosixTimeMs(posixTimeMs)
        if pos is None:
            print ('skipping record at time %s, no preceding positions available'
                   % TimeUtil.posixToUtcDateTime(posixTimeMs / 1000.0))
            return
        if posixTimeMs > maxTime:
            for tileParams in tile.getTilesOverlappingBounds((pos.longitude, pos.latitude,
                                                              pos.longitude, pos.latitude)):
                val = self.valueManager.getValue(obj)
                self.addSample(tileParams, pos, val)
                self.parent.delayBox.addJob((self.valueCode, tileParams))
            self.status['maxTime'] = max(maxTime, posixTimeMs)
            minTime = self.status['minTime'] or 99e+20
            self.status['minTime'] = min(minTime, posixTimeMs)
            self.status['numSamples'] += 1
            if self.status['numSamples'] % 100 == 0:
                print '%d %s tile update' % (self.status['numSamples'], self.valueCode)
        else:
            print ('skipping old (duplicate?) record: posixTimeMs %.3f <= maxTime %.3f'
                   % (posixTimeMs, self.status['maxTime']))

    def addSample(self, tileParams, pos, val):
        level, _x, _y = tileParams
        _x, _y, i, j = tile.getPixelOfLonLat(level, pos.longitude, pos.latitude)
        if not (0 <= i < N and 0 <= j < N):
            return

        tileKey = self.getTileKey(self.valueCode, tileParams)
        try:
            tileData = self.parent.store[tileKey]
        except KeyError:
            tileData = self.valueClass.makeTile(tileParams,
                                                self.meta['map']['smoothingMeters'],
                                                self.meta['map']['opaqueWeight'])
            self.status['numTiles'] += 1
        tileData.addSample(val, i, j)
        self.parent.store[tileKey] = tileData

    def getImage(self, tileData):
        signal, alpha = tileData.getSmoothed()

        signal = self.scaleAndClip(signal, self.colorRange)

        rgba = self.rgba
        rgba = matplotlib.cm.jet(signal, bytes=True)  # pylint: disable=E1101
        rgba[:, :, 3] = pilutil.bytescale(alpha, cmin=0.0, cmax=1.0)
        rgbaT = rgba.transpose((1, 0, 2)).copy()
        return Image.frombuffer('RGBA', (N, N), rgbaT,
                                'raw', 'RGBA', 0, 1)

    def writeOutputTile(self, tileParams):
        tileKey = self.getTileKey(self.valueCode, tileParams)
        tileData = self.parent.store[tileKey]
        im = self.getImage(tileData)

        level, x, y = tileParams
        outPath = '%s/%d/%d/%d.png' % (self.outputDir, level, x, y)
        outDir = os.path.dirname(outPath)
        if not os.path.exists(outDir):
            os.makedirs(outDir)
        im.save(outPath)

    def clean(self):
        # must call this before start() !
        assert not self.running

        plotUtil.rmIfPossible(self.outputDir)

    def flushQueue(self):
        while self.queue:
            self.indexRecord(self.queue.popleft())

    def batchIndex(self):
        # index everything in db that comes after the last thing we indexed on
        # the previous run
        print '--> batch indexing %s' % self.valueCode
        while 1:
            recs = self.queryManager.getData(minTime=self.status['maxTime'])
            n = recs.count()
            if n == 0:
                break
            print '--> %d %s samples remaining' % (n, self.valueCode)
            for rec in recs[:BATCH_READ_NUM_SAMPLES]:
                self.indexRecord(rec)

            # avoid django debug log memory leak
            db.reset_queries()

        # batch process new records that arrived while we were
        # processing the database table.
        print ('--> indexing %d %s samples that came in during batch indexing'
               % (len(self.inputQueue), self.valueCode))
        self.flushQueue()

        # switch modes to process each new record as it comes in.
        print '--> switching to live data mode'
        self.queueMode = False
