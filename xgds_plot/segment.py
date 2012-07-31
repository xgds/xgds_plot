# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

import math
import numpy
import sys
import time

from xgds_plot import settings

MIN_SEGMENT_LENGTH_MS = (settings.XGDS_PLOT_MIN_DATA_INTERVAL_MS
                         * settings.XGDS_PLOT_SEGMENT_RESOLUTION)

MIN_SEGMENT_LEVEL = int(math.log(MIN_SEGMENT_LENGTH_MS, 2))

MAX_SEGMENT_LEVEL = int(math.ceil(math.log(settings.XGDS_PLOT_MAX_SEGMENT_LENGTH_MS, 2))) + 1

LAST_DENOM_ZERO_WARNING_TIME = 0

HUGE_VALUE = 99e+20

class ScalarSegment(object):
    def __init__(self):
        self.n = settings.XGDS_PLOT_SEGMENT_RESOLUTION
        self.timeSum = numpy.zeros(self.n)
        self.sum = numpy.zeros(self.n)
        self.sqsum = numpy.zeros(self.n)
        self.min = numpy.zeros(self.n) + HUGE_VALUE
        self.max = numpy.zeros(self.n) - HUGE_VALUE
        self.count = numpy.zeros(self.n, dtype='l')

    def addSample(self, bucketIndex, posixTimeMs, val):
        self.timeSum[bucketIndex] += posixTimeMs
        self.sum[bucketIndex] += val
        self.sqsum[bucketIndex] += val * val

        self.min[bucketIndex] = min(self.min[bucketIndex], val)
        self.max[bucketIndex] = max(self.max[bucketIndex], val)
        self.count[bucketIndex] += 1

    def getMeanTimestamp(self, bucketIndex):
        return float(self.timeSum[bucketIndex]) / self.count[bucketIndex]

    def getMean(self, bucketIndex):
        return float(self.sum[bucketIndex]) / self.count[bucketIndex]

    def getVariance(self, bucketIndex):
        if self.count[bucketIndex] >= 2:
            return ((float(self.sqsum[bucketIndex]) / self.count[bucketIndex])
                    - (float(self.sum[bucketIndex]) / self.count[bucketIndex]) ** 2)
        else:
            return None

    def getJsonObj(self):
        fields = ['timestamp',
                  'mean',
                  'variance',
                  'min',
                  'max',
                  'count']
        data = [[self.getMeanTimestamp(i),
                 self.getMean(i),
                 self.getVariance(i),
                 self.min[i],
                 self.max[i],
                 self.count[i]]
                for i in xrange(self.n)
                if self.count[i] > 0]
        return {'fields': fields,
                'data': data}


class RatioSegment(ScalarSegment):
    def __init__(self):
        super(RatioSegment, self).__init__()
        self.numSum = numpy.zeros(self.n)
        self.denomSum = numpy.zeros(self.n)

    def addSample(self, bucketIndex, posixTimeMs, vals):
        global LAST_DENOM_ZERO_WARNING_TIME

        num, denom = vals

        self.timeSum[bucketIndex] += posixTimeMs
        self.numSum[bucketIndex] += num
        self.denomSum[bucketIndex] += denom
        self.count[bucketIndex] += 1

        if denom == 0:
            now = time.time()
            if now - LAST_DENOM_ZERO_WARNING_TIME > 5:
                print >> sys.stderr, 'warning: RatioSegment.addSample: denominator = 0, leaving sample out of some statistics to avoid divide by zero'
                LAST_DENOM_ZERO_WARNING_TIME = now
        else:
            val = float(num) / denom

            self.sum[bucketIndex] += val
            self.sqsum[bucketIndex] += val * val
            self.min[bucketIndex] = min(self.min[bucketIndex], val)
            self.max[bucketIndex] = max(self.max[bucketIndex], val)

    def getMean(self, bucketIndex):
        if self.denomSum[bucketIndex] == 0:
            return None
        else:
            return float(self.numSum[bucketIndex]) / self.denomSum[bucketIndex]

    def getMin(self, bucketIndex):
        minVal = self.min[bucketIndex]
        if minVal == HUGE_VALUE:
            return None
        else:
            return minVal

    def getMax(self, bucketIndex):
        maxVal = self.max[bucketIndex]
        if maxVal == -HUGE_VALUE:
            return None
        else:
            return maxVal

    def getJsonObj(self):
        fields = ['timestamp',
                  'mean',
                  'variance',
                  'min',
                  'max',
                  'count',
                  'numSum',
                  'denomSum']
        data = [[self.getMeanTimestamp(i),
                 self.getMean(i),
                 self.getVariance(i),
                 self.getMin(i),
                 self.getMax(i),
                 self.count[i],
                 self.numSum[i],
                 self.denomSum[i]]
                for i in xrange(self.n)
                if self.count[i] > 0]
        return {'fields': fields,
                'data': data}
