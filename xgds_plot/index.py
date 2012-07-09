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

from geocamUtil import anyjson as json
from geocamUtil.loader import getClassByName
from geocamUtil.store import FileStore, LruCacheStore
from geocamUtil.zmq.delayBox import DelayBox

from xgds_plot import settings

MIN_SEGMENT_LENGTH_MS = (settings.XGDS_PLOT_MIN_DATA_INTERVAL_MS
                         * settings.XGDS_PLOT_SEGMENT_RESOLUTION)

MIN_SEGMENT_LEVEL = int(math.log(MIN_SEGMENT_LENGTH_MS, 2))

MAX_SEGMENT_LEVEL = int(math.ceil(math.log(settings.XGDS_PLOT_MAX_SEGMENT_LENGTH_MS, 2))) + 1

DATA_PATH = os.path.join(settings.DATA_DIR,
                         settings.XGDS_PLOT_DATA_SUBDIR)

SEGMENTS_IN_MEMORY_PER_TIME_SERIES = 100

# CompactFloat/compactFloats: annoying hack to avoid printing out bogus
# extra digits when floats are embedded in JSON objects.
# http://stackoverflow.com/questions/1447287/format-floats-with-standard-json-module

class CompactFloat(float):
    def __repr__(self):
        return '%.15g' % self


def compactFloats(obj):
    if isinstance(obj, float):
        return CompactFloat(obj)
    elif isinstance(obj, dict):
        return dict((k, compactFloats(v)) for k, v in obj.items())
    elif isinstance(obj, (list, tuple)):
        return map(compactFloats, obj)
    return obj


def rmIfPossible(path):
    print '  deleting %s' % path
    try:
        shutil.rmtree(path)
    except OSError, oe:
        print >> sys.stderr, 'Failed to remove %s: %s' % (path, oe)


class JsonStore(object):
    def __init__(self, path):
        self.path = os.path.realpath(path)

    def write(self, obj):
        pathDir = os.path.dirname(self.path)
        if not os.path.exists(pathDir):
            os.makedirs(pathDir)
        json.dump(obj, open(self.path, 'wb'), indent=4, sort_keys=True)

    def read(self, dflt=None):
        if os.path.exists(self.path):
            return json.load(open(self.path, 'rb'))
        else:
            return dflt


class TimeSeriesIndex(object):
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
                                     'cache',
                                     self.valueCode)
        self.segmentDir = os.path.join(DATA_PATH,
                                       'plot',
                                       self.valueCode)
        self.delayBox = DelayBox(self.writeOutputSegment,
                                 maxDelaySeconds=1,
                                 numBuckets=10)

        self.queue = deque()
        self.running = False

    def start(self):
        self.store = LruCacheStore(FileStore(self.cacheDir),
                                   SEGMENTS_IN_MEMORY_PER_TIME_SERIES)
        self.delayBox.start()
        if self.subscriber:
            self.subscriber.subscribeDjango(self.meta['queryModel'] + ':',
                                            lambda topic, obj: self.handleRecord(obj))
        self.running = True

        self.statusPath = os.path.join(self.segmentDir,
                                       'status.json')
        self.statusStore = JsonStore(self.statusPath)
        self.status = self.statusStore.read(dflt={
            'maxPosixTimeMs': 0,
            'numRecords': 0,
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
        if queueMode:
            self.queue.append(obj)
        else:
            self.indexRecord(obj)

    def indexRecord(self, obj):
        posixTimeMs = self.queryManager.getTimestamp(obj)
        if posixTimeMs > self.status['maxPosixTimeMs']:
            for segmentIndex in self.getSegmentIndicesContainingTime(posixTimeMs):
                val = self.valueManager.getValue(obj)
                self.addSample(segmentIndex, posixTimeMs, val)
                self.delayBox.addJob(segmentIndex)
            self.status['maxPosixTimeMs'] = posixTimeMs
            self.status['numRecords'] += 1
            if self.status['numRecords'] % 100 == 0:
                print '%d segment update' % self.status['numRecords']
        else:
            print ('skipping old (duplicate?) record: posixTimeMs %.3f <= maxPosixTimeMs %.3f'
                   % (posixTimeMs, self.status['maxPosixTimeMs']))

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
        json.dump(compactFloats(segmentData.getJsonObj()),
                  open(outPath, 'wb'),
                  **styleArgs)

    def clean(self):
        # must call this before start() !
        assert not self.running

        rmIfPossible(self.cacheDir)
        rmIfPossible(self.segmentDir)

    def flushQueue(self):
        while self.queue:
            self.indexRecord(self.queue.popleft())

    def batchIndex(self):
        # index everything in db that comes after the last thing we indexed on
        # the previous run
        for rec in self.queryManager.getData(minTime=self.status['maxPosixTimeMs']):
            self.indexRecord(rec)

        # batch process new records that arrived while we were
        # processing the database table.
        self.flushQueue()

        # switch modes to process each new record as it comes in.
        self.queueMode = False
