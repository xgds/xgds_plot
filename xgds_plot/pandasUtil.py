# __BEGIN_LICENSE__
#Copyright © 2015, United States Government, as represented by the 
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

import logging
import copy

import numpy as np
import pandas as pd
import pandas.io.sql as psql
import MySQLdb
from django.conf import settings
try:
    from matplotlib import pyplot as plt
except ImportError:
    pass  # non-plotting functions should still work

# pylint: disable=R0924,W0108,E1101

_djangoDbSettings = settings.DATABASES['default']
DB_SETTINGS = dict(host=_djangoDbSettings['HOST'],
                   port=int(_djangoDbSettings['PORT']),
                   user=_djangoDbSettings['USER'],
                   passwd=_djangoDbSettings['PASSWORD'],
                   db=_djangoDbSettings['NAME'])
dbConnectionG = None


def getDbConnection():
    """
    Lazily initializes and caches a default db connection.
    """
    global dbConnectionG
    if not dbConnectionG:
        dbConnectionG = MySQLdb.connect(**DB_SETTINGS)
    return dbConnectionG


def closeDbConnection():
    """
    If there is an active default db connection, try to close it.

    May be useful to make long-running db clients more robust, avoiding
    any problems with stale connections, for example if the db server is
    restarted.
    """
    global dbConnectionG
    if dbConnectionG:
        try:
            dbConnectionG.close()
        except:  # pylint: disable=W0702
            logging.warning('pandasUtil.closeDbConnection: unable to close dbConnectionG %s', dbConnectionG)
            logging.warning('pandasUtil.closeDbConnection: will dereference current connection and use a new one')
        dbConnectionG = None


def quoteIfString(obj):
    if isinstance(obj, (str, unicode)):
        return '"%s"' % obj
    else:
        return obj


def rejectOutliers(frame, fieldName,
                   percent=1,
                   rejectLow=True,
                   rejectHigh=True):
    field = getattr(frame, fieldName)
    lo, hi = np.percentile(field, [percent, 100 - percent])
    filt = True
    if rejectLow:
        filt = np.logical_and(filt, lo <= field)
    if rejectHigh:
        filt = np.logical_and(filt, field <= hi)
    return frame[filt]


class AbstractFrameSource(object):
    """
    A AbstractFrameSource acts like a Django object manager, but instead
    of returning a Django QuerySet object, it returns an XgdsFrame
    object designed for easy plotting.

    Familiar Django methods filter() and array slicing ([:10] -> SQL
    LIMIT 10) work unchanged. In order to finalize the query you either
    call getFrame() to get a frame with an arbitrary number of records,
    or getRecord() to get a frame expected to contain a single record
    and extract that record.

    Much like Django QuerySet, we do some caching. If you want the same
    AbstractFrameSource but with an empty cache, call source.copy().

    The postProcess() method is designed to enable model-specific
    post-processing in derived classes. (Applied after the data is
    received from the database and before returning the XgdsFrame.)
    """

    def __init__(self, model, parent=None):
        self._name = model.__name__
        self.parent = parent
        self.model = model
        self.qset = None
        self.cache = {}

    def copy(self):
        result = type(self)(self.model, self.parent)
        result.qset = copy.deepcopy(self.qset)
        return result

    def reset(self):
        self.qset = None
        self.cache = {}

    def _getQset(self):
        if self.qset is None:
            self.qset = self.model.objects.all()
            filtered = self.parent._apply(self)
            self.qset = filtered.qset
        return self.qset

    def _replaceQset(self, qset):
        result = self.copy()
        result.qset = qset
        return result

    def getSql(self):
        # str(self.qset.query) usually works but quoting seems to be
        # messed up if you have a string parameter.
        query, params = self._getQset().query.sql_with_params()
        params = tuple([quoteIfString(obj) for obj in params])
        return query % params

    def filter(self, *args, **kwargs):
        return self._replaceQset(self._getQset().filter(*args, **kwargs))

    def __getitem__(self, k):
        return self._replaceQset(self._getQset()[k])

    def getDataWithCache(self, sql):
        result = self.cache.get(sql)
        if result is None:
            result = psql.frame_query(sql, con=getDbConnection())
            result = self.postProcess(result)
            self.cache[sql] = result
        return result

    def getFrame(self, *args, **kwargs):
        if args or kwargs:
            filtered = self.filter(*args, **kwargs)
        else:
            filtered = self
        sql = filtered.getSql()
        logging.debug('getFrame: %s', sql)
        return self.getDataWithCache(sql)

    def filterTime(self, start=None, end=None):
        timestampField = 'timestamp'  # FIX: don't hard code
        result = self
        if start:
            result = result.filter(**{timestampField + '__gte': start})
        if end:
            result = result.filter(**{timestampField + '__lte': end})
        return result

    def rejectOutliers(self, fieldName,
                       percent=1,
                       rejectLow=True,
                       rejectHigh=True):
        return rejectOutliers(self.getFrame(),
                              fieldName,
                              percent,
                              rejectLow,
                              rejectHigh)

    def getRecord(self, *args, **kwargs):
        frame = self.getFrame(*args, **kwargs)
        if len(frame) != 1:
            raise ValueError('getRecord() query returned %s matches, expected exactly 1'
                             % len(frame))
        return frame.xs(0)

    def _getField(self, name):
        return getattr(self.getFrame(), name)

    def _setLabelToVerboseName(self, frame):
        for f in self.model._meta.fields:
            if hasattr(frame, f.name):
                column = getattr(frame, f.name)
                setattr(column, 'label', f.verbose_name)

    def postProcess(self, result):
        return result


def makeFrameSourceDerivedClass(djangoModel, baseClass):
    """
    Make a derived FrameSource class, adding properties based on
    the fields available in the given Django model.
    """

    # work-around for python closure scope issue
    def getLambda(name):
        return lambda self: self._getField(name)

    props = {}
    for f in djangoModel._meta.fields:
        props[f.name] = property(getLambda(f.name))

    derivedClassName = djangoModel.__name__ + 'FrameSource'
    derivedClass = type(derivedClassName,
                        (baseClass,),
                        props)

    return derivedClass


class QuerySetLike(object):
    """
    A QuerySetLike has methods similar to a Django QuerySet but simply
    stores a history of what you call on it.  You can use the _apply()
    method to _apply the same calls to an actual QuerySet later.

    Example usage:
      x = QuerySetLike()
      y = x.filter(foo='bar')
      z = y[:10]
      filteredQuerySet = z.apply(SomeDjangoModel.objects)
    """

    def __init__(self):
        self._ops = []

    def copy(self):
        return copy.deepcopy(self)

    def _appendOp(self, methodName, args, kwargs):
        result = self.copy()
        result._ops.append((methodName, args, kwargs))
        return result

    def filter(self, *args, **kwargs):
        return self._appendOp('filter', args, kwargs)

    def filterTime(self, *args, **kwargs):
        return self._appendOp('filterTime', args, kwargs)

    def __getitem__(self, k):
        return self._appendOp('__getitem__', [k], {})

    def _apply(self, qset):
        for methodName, args, kwargs in self._ops:
            method = getattr(qset, methodName)
            qset = method(*args, **kwargs)
        return qset


class AbstractTimeSeriesSource(object):
    def __init__(self, frameSource, valueFieldName):
        self._frameSource = frameSource
        self._valueFieldName = valueFieldName
        self._frameCache = None

    def _getFrame(self):
        if self._frameCache is None:
            self._frameCache = self._frameSource.getFrame()
        return self._frameCache

    def _getField(self, fname):
        return getattr(self._getFrame(), fname)

    def _getValueField(self):
        return self._getField(self._valueFieldName)

    frame = property(_getFrame)
    value = property(_getValueField)


def makeTimeSeriesSourceDerivedClass(djangoModel, baseClass):
    """
    Make a derived TimeSeriesSource class, adding properties based on
    the fields available in the given Django model.
    """

    # work-around for python closure scope issue
    def getLambda(name):
        return lambda self: self._getField(name)

    props = {}
    for f in djangoModel._meta.fields:
        props[f.name] = property(getLambda(f.name))

    derivedClassName = djangoModel.__name__ + 'TimeSeriesSource'
    derivedClass = type(derivedClassName,
                        (baseClass,),
                        props)

    return derivedClass


class Data(QuerySetLike):
    def __init__(self,
                 frameSourceBaseClass=AbstractFrameSource,
                 timeSeriesSourceBaseClass=AbstractTimeSeriesSource):
        super(Data, self).__init__()
        self._frameSourceBaseClass = frameSourceBaseClass
        self._timeSeriesSourceBaseClass = timeSeriesSourceBaseClass

    def _addModel(self, model):
        frameSourceClass = makeFrameSourceDerivedClass(model,
                                                       self._frameSourceBaseClass)
        frameSource = frameSourceClass(model, self)
        setattr(self, model.__name__, frameSource)

    def getVariable(self, frameSource, valueFieldName):
        timeSeriesClass = makeTimeSeriesSourceDerivedClass(frameSource.model,
                                                           self._timeSeriesSourceBaseClass)
        return timeSeriesClass(frameSource, valueFieldName)

    def _addVariable(self, frameSource, valueFieldName):
        setattr(self, valueFieldName, self.getVariable(frameSource, valueFieldName))


def _applyLabel(x, labelFunc):
    label = getattr(x, 'label', None)
    if not label:
        label = getattr(x, 'name', None)
    if label:
        labelFunc(label)


def xplot(x, y, *args, **kwargs):
    plt.plot(x, y, *args, **kwargs)
    _applyLabel(x, plt.xlabel)
    _applyLabel(y, plt.ylabel)
    # default figure size for time series plots
    plt.gcf().set_size_inches(20, 3)


def xscatter(x, y, c='b', *args, **kwargs):
    plt.scatter(x, y, c=c,
                *args, **kwargs)
    if not isinstance(c, str):
        cb = plt.colorbar()
        _applyLabel(c, lambda label: cb.ax.set_ylabel(label))
    _applyLabel(x, plt.xlabel)
    _applyLabel(y, plt.ylabel)
    # default figure size for scatter plots
    plt.gcf().set_size_inches(5, 4)


def xheatmap(x, y, bins=30, **kwargs):
    valid = np.logical_and(pd.notnull(x), pd.notnull(y))
    heatmap, xedges, yedges = np.histogram2d(x[valid],
                                             y[valid],
                                             bins=bins)
    heatmap = np.rot90(heatmap)  # histogram2d output is weird
    extent = [xedges[0], xedges[-1], yedges[0], yedges[-1]]
    im = plt.imshow(heatmap, extent=extent, aspect='auto')
    _applyLabel(x, plt.xlabel)
    _applyLabel(y, plt.ylabel)
    cb = plt.colorbar(im)
    cb.ax.set_ylabel('Counts')


def xhist(x, **kwargs):
    plt.hist(x, **kwargs)
    _applyLabel(x, plt.xlabel)
    plt.ylabel('Counts')


def _getFrameFromDataSet(dataSet):
    for methodName in ('getFrame', '_getFrame'):
        method = getattr(dataSet, methodName, None)
        if method:
            return method()
    return dataSet


def xjoin(dataSets, resample='30min'):
    result = _getFrameFromDataSet(dataSets[0]).resample(resample)
    for i, dataSet in enumerate(dataSets[1:]):
        frame = _getFrameFromDataSet(dataSet).resample(resample)
        result = result.join(frame, how='left', rsuffix='_%s' % i)
    return result
