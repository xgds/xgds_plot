# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

import os
import math
import numpy
import shutil
import sys
from collections import deque
import time

from django import db

from geocamUtil import anyjson as json
from geocamUtil.loader import getClassByName
from geocamUtil.store import FileStore, LruCacheStore
from geocamUtil.zmq.delayBox import DelayBox

from xgds_plot import settings
from xgds_plot import plotUtil

MIN_SEGMENT_LENGTH_MS = (settings.XGDS_PLOT_MIN_DATA_INTERVAL_MS
                         * settings.XGDS_PLOT_SEGMENT_RESOLUTION)

MIN_SEGMENT_LEVEL = int(math.log(MIN_SEGMENT_LENGTH_MS, 2))

MAX_SEGMENT_LEVEL = int(math.ceil(math.log(settings.XGDS_PLOT_MAX_SEGMENT_LENGTH_MS, 2))) + 1

DATA_PATH = os.path.join(settings.DATA_DIR,
                         settings.XGDS_PLOT_DATA_SUBDIR)

SEGMENTS_IN_MEMORY_PER_TIME_SERIES = 100

BATCH_READ_NUM_SAMPLES = 5000
BATCH_SLEEP_NUM_SAMPLES = 100
BATCH_SLEEP_TIME_FACTOR = 3

class SegmentIndex(object):
    @classmethod
    def getKeyFromSegmentIndex(cls, segmentIndex):
        level, t = segmentIndex
        return '%s_%s' % (level, t)

    @classmethod
    def getSegmentIndexContainingTime(cls, level, posixTimeMs):
        segmentLength = 2.0 ** level
        return (level, int(posixTimeMs / segmentLength))

    @classmethod
    def getBucketIndexContainingTime(cls, level, posixTimeMs):
        segmentLength = 2.0 ** level
        segVal = posixTimeMs / segmentLength
        segmentNum = int(segVal)
        bucketIndex = int((segVal - int(segVal)) * settings.XGDS_PLOT_SEGMENT_RESOLUTION)
        return bucketIndex

    @classmethod
    def getSegmentIndicesContainingTime(cls, posixTimeMs):
        return [cls.getSegmentIndexContainingTime(level, posixTimeMs)
                for level in xrange(MIN_SEGMENT_LEVEL, MAX_SEGMENT_LEVEL)]

    def __init__(self, meta, subscriber, batchIndexAtStart=True):
        self.meta = meta
        self.subscriber = subscriber
        self.queueMode = batchIndexAtStart

        queryClass = getClassByName(self.meta['queryType'])
        self.queryManager = queryClass(self.meta)

        valueClass = getClassByName(self.meta['valueType'])
        self.valueManager = valueClass(self.meta,
                                       self.queryManager)

        self.valueCode = self.meta['valueCode']
        self.cacheDir = os.path.join(DATA_PATH,
                                     'plot',
                                     'cache',
                                     self.valueCode)
        self.segmentDir = os.path.join(DATA_PATH,
                                       'plot',
                                       self.valueCode)
        self.delayBox = DelayBox(self.writeOutputSegment,
                                 maxDelaySeconds=5,
                                 numBuckets=10)

        self.queue = deque()
        self.running = False

    def start(self):
        self.store = LruCacheStore(FileStore(self.cacheDir),
                                   SEGMENTS_IN_MEMORY_PER_TIME_SERIES)
        self.delayBox.start()
        if self.subscriber:
            self.queryManager.subscribeDjango(self.subscriber,
                                              lambda topic, obj: self.handleRecord(obj))

        self.running = True

        self.statusPath = os.path.join(self.segmentDir,
                                       'status.json')
        self.statusStore = plotUtil.JsonStore(self.statusPath)
        self.status = self.statusStore.read(dflt={
            'minTime': None,
            'maxTime': None,
            'numSamples': 0,
            'numSegments': 0
        })

        if self.queueMode:
            self.batchIndex()

    def stop(self):
        if self.running:
            self.store.sync()
            self.delayBox.stop()
            self.statusStore.write(self.status)
            self.running = False

    def handleRecord(self, obj):
        if self.queueMode:
            self.queue.append(obj)
        else:
            self.indexRecord(obj)

    def indexRecord(self, obj):
        if (self.queueMode
            and (self.status['numSamples'] % BATCH_SLEEP_NUM_SAMPLES) == 0):
            batchProcessDuration = time.time() - self.batchProcessStartTime
            sleepTime = batchProcessDuration * BATCH_SLEEP_TIME_FACTOR
            print 'sleeping for %.3f seconds to avoid overloading server' % sleepTime
            time.sleep(sleepTime)
            self.batchProcessStartTime = time.time()

        posixTimeMs = self.queryManager.getTimestamp(obj)
        maxTime = self.status['maxTime'] or -99e+20
        if posixTimeMs <= maxTime:
            print ('skipping old (duplicate?) record: posixTimeMs %.3f <= maxTime %.3f'
                   % (posixTimeMs, self.status['maxTime']))
            return

        self.status['maxTime'] = max(maxTime, posixTimeMs)
        minTime = self.status['minTime'] or 99e+20
        self.status['minTime'] = min(minTime, posixTimeMs)
        self.status['numSamples'] += 1
        if self.status['numSamples'] % 100 == 0:
            print '%d %s segment update' % (self.status['numSamples'], self.valueCode)

        for segmentIndex in self.getSegmentIndicesContainingTime(posixTimeMs):
            val = self.valueManager.getValue(obj)
            self.addSample(segmentIndex, posixTimeMs, val)
            self.delayBox.addJob(segmentIndex)

    def addSample(self, segmentIndex, posixTimeMs, val):
        segmentKey = self.getKeyFromSegmentIndex(segmentIndex)
        try:
            segmentData = self.store[segmentKey]
        except KeyError:
            segmentData = self.valueManager.makeSegment()
            self.status['numSegments'] += 1
        level, t = segmentIndex
        bucketIndex = self.getBucketIndexContainingTime(level, posixTimeMs)
        segmentData.addSample(bucketIndex, posixTimeMs, val)
        self.store[segmentKey] = segmentData

    def writeJsonWithTmp(self, outPath, obj, styleArgs={}):
        tmpPath = outPath + '.part'
        json.dump(plotUtil.compactFloats(obj),
                  open(tmpPath, 'wb'),
                  **styleArgs)
        os.rename(tmpPath, outPath)

    def writeOutputSegment(self, segmentIndex):
        level, t = segmentIndex
        segmentKey = self.getKeyFromSegmentIndex(segmentIndex)
        segmentData = self.store[segmentKey]
        outPath = '%s/%d/%d.json' % (self.segmentDir, level, t)
        outDir = os.path.dirname(outPath)
        if not os.path.exists(outDir):
            os.makedirs(outDir)
        if settings.XGDS_PLOT_PRETTY_PRINT_JSON_SEGMENTS:
            styleArgs = dict(sort_keys=True,
                             indent=4)
        else:
            styleArgs = dict(separators=(',', ':'))
        self.writeJsonWithTmp(outPath, segmentData.getJsonObj(), styleArgs)

    def clean(self):
        # must call this before start() !
        assert not self.running

        plotUtil.rmIfPossible(self.cacheDir)
        plotUtil.rmIfPossible(self.segmentDir)

    def flushQueue(self):
        while self.queue:
            self.indexRecord(self.queue.popleft())

    def batchIndex(self):
        self.batchProcessStartTime = time.time()

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
               % (len(self.queue), self.valueCode))
        self.flushQueue()

        # switch modes to process each new record as it comes in.
        print '--> switching to live data mode'
        self.queueMode = False
