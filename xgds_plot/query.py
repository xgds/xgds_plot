# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

from geocamUtil.modelUtil import getModelByName

class TimeSeriesQuery(object):
    """
    TimeSeriesQuery is an abstract base class for classes that support
    time series queries in xgds_plot.
    """
    def __init__(self, meta):
        """
        Initialize object with meta-data from settings.
        """
        raise NotImplementedError()

    def getData(minTime=None, maxTime=None):
        """
        Return an iterable containing the records in the specified
        time interval. Both @minTime and @maxTime are optional.
        """
        raise NotImplementedError()


class Django(TimeSeriesQuery):
    """
    A TimeSeriesQuery implementation that retrieves data from a Django
    model.

    This is the default implementation we use if the "queryType" parameter
    is not specified.
    """
    def __init__(self, meta):
        self.model = getModelByName(meta['queryModel'])
        self.timestampField = meta['queryTimestampField']

    def getData(minTime=None, maxTime=None):
        filterKwargs = {}
        if minTime is not None:
            filterKwargs[self.timestampField + '__gte'] = minTime
        if maxTime is not None:
            filterKwargs[self.timestampField + '__lte'] = maxTime
        return self.model.objects.filter(**filterKwargs)
