# __BEGIN_LICENSE__
#Copyright (c) 2015, United States Government, as represented by the 
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

from django.db import connection

from geocamUtil.loader import getModelByName
from geocamUtil import TimeUtil

from django.conf import settings

# pylint: disable=W0231


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

    def getData(self, minTime=None, maxTime=None):
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


def capitalizeFirstLetter(s):
    return s[:1].capitalize() + s[1:]


def getMin(a, b):
    if a is None:
        return b
    elif b is None:
        return a
    else:
        return min(a, b)


def getMax(a, b):
    if a is None:
        return b
    elif b is None:
        return a
    else:
        return max(a, b)


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
        self.timestampMicrosecondsField = meta.get('queryTimestampMicrosecondsField', None)
        self.timestampNanosecondsField = meta.get('queryTimestampNanosecondsField', None)
        self.startTime = meta.get('startTime', None)
        self.endTime = meta.get('endTime', None)

        self.filterDict = dict(meta.get('queryFilter', []))
        self.queryTopic = meta['queryModel']
        queryFilter = meta.get('queryFilter', [])
        for _field, value in queryFilter:
            self.queryTopic += '.%s' % value
        self.queryTopic += ':'

    def getValueName(self, valueField):
        return capitalizeFirstLetter(self.model._meta.get_field(valueField).verbose_name)

    def getData(self, minTime=None, maxTime=None):
        minTime = getMax(self.startTime, minTime)
        maxTime = getMin(self.endTime, maxTime)

        filterKwargs = {}
        if minTime is not None:
            filterKwargs[self.timestampField + '__gt'] = posixTimeMsToUtcDateTime(minTime)
        if maxTime is not None:
            filterKwargs[self.timestampField + '__lte'] = posixTimeMsToUtcDateTime(maxTime)
        if self.filterDict:
            filterKwargs.update(self.filterDict)
        return self.model.objects.filter(**filterKwargs).order_by(self.timestampField)

    def getDatesWithData(self):
        cursor = connection.cursor()
        cursor.execute("SELECT DISTINCT DATE(CONVERT_TZ(%s, 'UTC', '%s')) FROM %s"
                       % (self.timestampField,
                          settings.XGDS_PLOT_OPS_TIME_ZONE,
                          self.model._meta.db_table))
        dates = [fields[0] for fields in cursor.fetchall()]
        #if self.startTime:
        #    dates = [day for day in dates if day > posixTimeMsToUtcDateTime(self.startTime)]
        #if self.endTime:
        #    dates = [day for day in dates if day <= posixTimeMsToUtcDateTime(self.endTime)]
        return dates

    def getTimestamp(self, obj):
        utcDt = getattr(obj, self.timestampField)
        posixTimeSecs = TimeUtil.utcDateTimeToPosix(utcDt)
        posixTimeMs = posixTimeSecs * 1000
        if self.timestampMicrosecondsField is not None:
            microseconds = getattr(obj, self.timestampMicrosecondsField)
            assert microseconds <= 1e+6
            posixTimeMs += microseconds * 1e-3
        elif self.timestampNanosecondsField is not None:
            nanoseconds = getattr(obj, self.timestampNanosecondsField)
            assert nanoseconds <= 1e+9
            posixTimeMs += nanoseconds * 1e-6
        return posixTimeMs

    def subscribeDjango(self, subscriber, func):
        subscriber.subscribeDjango(self.queryTopic,
                                   func)
