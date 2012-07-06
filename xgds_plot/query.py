# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

from geocamUtil.loader import getModelByName
from geocamUtil import TimeUtil

def posixTimeMsToUtcDateTime(posixTimeMs):
    return TimeUtil.posixToUtcDateTime(posixTimeMs / 1000.0)


class TimeSeriesQueryManager(object):
    """
    TimeSeriesQueryManager is an abstract base class for classes that
    support time series queries in xgds_plot.
    """
    def __init__(self, meta):
        """
        Initialize object with meta-data from settings. Note: May normalize
        settings.
        """
        raise NotImplementedError()

    def getValueName(self, valueField):
        """
        Return a human-readable name for the specified field (assuming
        the time series supports introspection).
        """
        raise NotImplementedError()

    def getData(minTime=None, maxTime=None):
        """
        Return an iterable containing the records in the specified time
        interval, in order of increasing time. Both @minTime and
        @maxTime are optional. If specified they must be datetimes.
        """
        raise NotImplementedError()

    def getTimestamp(self, obj):
        """
        Return the timestamp for a record.
        """
        raise NotImplementedError()


class Django(TimeSeriesQueryManager):
    """
    A TimeSeriesQueryManager implementation that retrieves data from a
    Django model.

    This is the default implementation we use if the "queryType" parameter
    is not specified in the settings.
    """
    def __init__(self, meta):
        self.model = getModelByName(meta['queryModel'])
        self.timestampField = meta['queryTimestampField']

    def getValueName(self, valueField):
        return self.model._meta.get_field(valueField).verbose_name

    def getData(self, minTime=None, maxTime=None):
        filterKwargs = {}
        if minTime is not None:
            filterKwargs[self.timestampField + '__gte'] = posixTimeMsToUtcDateTime(minTime)
        if maxTime is not None:
            filterKwargs[self.timestampField + '__lte'] = posixTimeMsToUtcDateTime(maxTime)
        return self.model.objects.filter(**filterKwargs).order_by(self.timestampField)

    def getTimestamp(self, obj):
        posixTimeSecs = TimeUtil.utcDateTimeToPosix(getattr(obj, self.timestampField))
        posixTimeMs = posixTimeSecs * 1000
        return posixTimeMs
