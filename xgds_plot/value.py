# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

from geocamUtil.loader import getModelByName


class TimeSeriesValueManager(object):
    """
    TimeSeriesValueManager is an abstract base class for classes that
    support time series values in xgds_plot. It knows how to extract the
    value or values of interest from a larger record.
    """
    def __init__(self, meta):
        """
        Initialize object with meta-data from settings. Note: May
        normalize settings.
        """
        raise NotImplementedError()

    def getValue(self, rec):
        """
        Extracts the desired value from a larger record.
        """
        raise NotImplementedError()

    def getBucket(self):
        """
        Return the right type of bucket to summarize statistics over values
        extracted by this manager.
        """
        raise NotImplementedError()


class TimeSeriesValueBucket(object):
    """
    TimeSeriesValueBucket is an abstract base class for classes that
    track statistics in xgds_plot. Each derived class knows how to
    calculate relevant statistics for a particular value type.
    """
    
    def addSample(self, rec):
        """
        Adds a sample for summary statistics.
        """
        raise NotImplementedError()

    def getMean(self):
        raise NotImplementedError()
    
    def getVariance(self):
        raise NotImplementedError()

    def getMin(self):
        raise NotImplementedError()

    def getMax(self):
        raise NotImplementedError()


class Scalar(TimeSeriesValueManager):
    def __init__(self, meta, queryManager):
        self.valueField = meta['valueField']
        self.queryManager = queryManager

        # normalize meta-data
        if 'valueCode' not in meta:
            meta['valueCode'] = self.valueField
        if 'valueName' not in meta:
            meta['valueName'] = self.queryManager.getValueName(meta['valueField'])

    def getValue(self, rec):
        return getattr(rec, self.valueField)

    def getBucket(self):
        return Bucket(self)

    class Bucket(TimeSeriesValueBucket):
        def __init__(self, parent):
            self.parent = parent
            self.sum = 0
            self.sqsum = 0
            self.min = None
            self.max = None
            self.count = 0

        def addSample(self, rec):
            val = self.parent.getValue(rec)
            self.sum += val
            self.sqsum += val * val

            if self.min is None:
                self.min = val
            else:
                self.min = min(self.min, val)

            if self.max is None:
                self.max = val
            else:
                self.max = max(self.max, val)
            self.count += 1

        def getMean(self):
            if self.count:
                return self.sum / self.count
            else:
                return None

        def getVariance(self):
            if self.count >= 2:
                return (self.sqsum / self.count) - (self.sum / self.count) ** 2
            else:
                return None

        def getMin(self):
            return self.min

        def getMax(self):
            return self.max

class Ratio(TimeSeriesValueManager):
    def __init__(self, meta, queryManager):
        self.numField, self.denomField = meta['valueFields']
        self.queryManager = queryManager

    def getValue(self, rec):
        return (getattr(rec, self.numField),
                getattr(rec, self.denomField))

    def getBucket(self):
        return Bucket(self)

    # FIX: specialize for ratio
    class Bucket(TimeSeriesValueBucket):
        def __init__(self, parent):
            self.parent = parent
            self.sum = 0
            self.sqsum = 0
            self.min = None
            self.max = None
            self.count = 0

        def addSample(self, rec):
            val = self.parent.getValue(rec)
            self.sum += val
            self.sqsum += val * val

            if self.min is None:
                self.min = val
            else:
                self.min = min(self.min, val)

            if self.max is None:
                self.max = val
            else:
                self.max = max(self.max, val)
            self.count += 1

        def getMean(self):
            if self.count:
                return self.sum / self.count
            else:
                return None

        def getVariance(self):
            if self.count >= 2:
                return (self.sqsum / self.count) - (self.sum / self.count) ** 2
            else:
                return None

        def getMin(self):
            return self.min

        def getMax(self):
            return self.max
