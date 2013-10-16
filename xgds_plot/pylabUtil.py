#!/usr/bin/env python
# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

import numpy as np
import scipy as sp
import pytz
import matplotlib.dates
import django.db.models
from matplotlib import pyplot as plt

from xgds_plot.plotUtil import *  # pylint: disable=W0401
from xgds_plot import settings

# pylint: disable=E1101,W0201,R0924,W0108


class ShortDateFormatter(matplotlib.dates.AutoDateFormatter):
    def __call__(self, x, pos=0):
        scale = float(self._locator._get_unit())

        d = matplotlib.dates.DateFormatter
        if (scale >= 365.0):
            self._formatter = d("%Y", self._tz)
        elif (scale == 30.0):
            self._formatter = d("%b %Y", self._tz)
        elif ((scale == 1.0) or (scale == 7.0)):
            self._formatter = d("%b %d", self._tz)
        elif (scale == (1.0 / 24.0)):
            self._formatter = d("%H:%M", self._tz)
        elif (scale == (1.0 / (24 * 60))):
            self._formatter = d("%H:%M", self._tz)
        elif (scale == (1.0 / (24 * 3600))):
            self._formatter = d("%M:%S", self._tz)
        else:
            self._formatter = d("%b %d %Y %H:%M:%S", self._tz)

        return self._formatter(x, pos)


def setXAxisDateFormatter(ax):
    ax.xaxis_date(tz=pytz.utc)
    loc = matplotlib.dates.AutoDateLocator(interval_multiples=True)
    ax.xaxis.set_major_locator(loc)
    fmt = ShortDateFormatter(loc)
    ax.xaxis.set_major_formatter(fmt)


def firstcaps(val):
    return val[0].upper() + val[1:]


class PlotDataSet(object):
    def __init__(self, qset):
        self._qset = list(qset)
        assert self._qset
        self._n = len(self._qset)
        self.field = {}
        self.label = {}
        for fieldTuple in self._qset[0]._meta._field_cache:
            field = fieldTuple[0]
            self.field[field.name] = field
            self.label[field.name] = firstcaps(field.verbose_name)
        self._cache = {}
        self._timeOffset = float(settings.XGDS_PLOT_TIME_OFFSET_HOURS) / 24.0

    def getLabel(self, field):
        return self.label[field]

    def date2num(self, dt):
        return matplotlib.dates.date2num(dt) + self._timeOffset

    def getDataType(self, field):
        if isinstance(field, django.db.models.FloatField):
            return (np.float64, lambda val: val)
        if isinstance(field, (django.db.models.IntegerField,
                              django.db.models.PositiveIntegerField,
                              django.db.models.AutoField)):
            return (np.int64, lambda val: val)
        elif isinstance(field, django.db.models.DateTimeField):
            return (np.float64, self.date2num)
        else:
            return (np.float64, lambda val: val)

    def __getattr__(self, name):
        assert name in self.field
        dtype, converter = self.getDataType(self.field[name])
        dataSet = np.zeros(self._n, dtype=dtype)
        for i, rec in enumerate(self._qset):
            dataSet[i] = converter(getattr(rec, name))

        setattr(self, name, dataSet)
        return dataSet

    def __getitem__(self, name):
        return getattr(self, name)


def percentile(vec, pct):
    """
    Sort of like np.percentile, back-ported to older versions of
    np.
    """
    vec = sorted(vec)
    n = len(vec)
    if isinstance(pct, (float, int)):
        pct = np.array(pct)
    result = np.zeros(len(pct))
    for j, p in enumerate(pct):
        pos = float(p) / 100 * (n - 1)
        i = min(int(pos), n - 2)
        weight = pos - i
        result[j] = vec[i] * (1 - weight) + vec[i + 1] * weight
    return result


def extendRange(rng, proportion):
    rngMin, rngMax = rng
    dist = rngMax - rngMin
    return (rngMin - proportion * dist,
            rngMax + proportion * dist)


def rejectOutliers(vec, pctOutliers=1.0, extendProportion=0.05):
    return (extendRange
            (percentile(vec, [pctOutliers, 100 - pctOutliers]),
             extendProportion))


class LazyAttributes(object):
    def __init__(self):
        self._lazyAttributes = {}

    def setLazy(self, attrName, func):
        self._lazyAttributes[attrName] = func

    def __getattr__(self, attrName):
        assert attrName != '_lazyAttributes', '_lazyAttributes member not initialized; do you call the LazyAttributes constructor in the constructor for your derived class?'
        func = self._lazyAttributes.get(attrName, None)
        if func is None:
            raise AttributeError(attrName)
        val = func()
        setattr(self, attrName, val)
        return val


class XgdsPlotTimeSeries(LazyAttributes):
    def __init__(self, name, label, dataFunc=None, data=None, timestamp=None, timeOfDay=None, isDate=False):
        super(XgdsPlotTimeSeries, self).__init__()
        self.name = name
        self.label = label
        self.dataFunc = dataFunc
        if data is not None:
            self.data = data
        self.timestamp = timestamp
        self.timeOfDay = timeOfDay
        self.isDate = isDate

        if dataFunc is not None and data is None:
            self.setLazy('data', dataFunc)

    def copy(self):
        result = XgdsPlotTimeSeries(self.name, self.label, self.dataFunc,
                                    self.data, self.timestamp,
                                    self.timeOfDay, self.isDate)
        if hasattr(self, 'data'):
            result.data = self.data
        return result

    def rejectOutliers(self, bottomPercentile=1.0, topPercentile=1.0):
        bottomVal, topVal = percentile(self.data, [bottomPercentile, 100 - topPercentile])
        outOfRange = np.logical_or(self.data < bottomVal,
                                   self.data > topVal)

        result = self.copy()
        result.data = np.ma.masked_array(self.data, outOfRange)
        return result


class XgdsPlotModel(LazyAttributes):
    def __init__(self, djangoModel):
        super(XgdsPlotModel, self).__init__()
        self._djangoModel = djangoModel
        self.initQuery()
        self._qresult = None

        fields = [fieldTuple[0] for fieldTuple in self._djangoModel._meta._field_cache]
        self._fieldDict = dict([(field.name, field) for field in fields])
        timestampField = self._fieldDict['timestamp']
        self.timestamp = XgdsPlotTimeSeries('timestamp',
                                            'Timestamp (%s)' % settings.XGDS_PLOT_TIME_ZONE_NAME,
                                            lambda: self.getData(timestampField),
                                            isDate=True)
        self.timeOfDay = XgdsPlotTimeSeries('timeOfDay',
                                            'Time of day (hours, %s)' % settings.XGDS_PLOT_TIME_ZONE_NAME,
                                            lambda: np.mod(self.timestamp.data, 1) * 24,
                                            timestamp=self.timestamp)

        # work-around for brain-dead python closure scoping
        def makeLambda(f):
            return lambda: self.getData(f)

        for field in fields:
            if field.name == 'timestamp':
                continue
            isDate = isinstance(field, django.db.models.DateTimeField)
            setattr(self,
                    field.name,
                    XgdsPlotTimeSeries(field.name,
                                       self.getLabel(field),
                                       makeLambda(field),
                                       timestamp=self.timestamp,
                                       timeOfDay=self.timeOfDay,
                                       isDate=isDate))

        self._timeOffset = float(settings.XGDS_PLOT_TIME_OFFSET_HOURS) / 24.0

    def initQuery(self):
        self._qset = self._djangoModel.objects.all().order_by('timestamp')
        self._qresult = None

    def runQuery(self):
        if self._qresult is None:
            self._qresult = list(self._qset)

    def filter(self, **kwargs):
        assert self._qresult is None, 'must apply filters before query is run (i.e. before using data sets)'
        self._qset = self._qset.filter(**kwargs)

    def filterTime(self, start=None, end=None):
        if isinstance(start, (str, unicode)):
            start = parseTime(start)
        if isinstance(end, (str, unicode)):
            end = parseTime(end)

        if start is not None:
            self.filter(timestamp__gte=start)
        if end is not None:
            self.filter(timestamp__lte=end)

    def getLabel(self, field):
        return firstcaps(field.verbose_name)

    def date2num(self, dt):
        return matplotlib.dates.date2num(dt) + self._timeOffset

    def getDataType(self, field):
        if isinstance(field, django.db.models.FloatField):
            return (np.float64, lambda val: val)
        if isinstance(field, (django.db.models.IntegerField,
                              django.db.models.PositiveIntegerField,
                              django.db.models.AutoField)):
            return (np.int64, lambda val: val)
        elif isinstance(field, django.db.models.DateTimeField):
            return (np.float64, self.date2num)
        else:
            return (np.float64, lambda val: val)

    def getData(self, field):
        dtype, converter = self.getDataType(field)
        self.runQuery()
        dataSet = np.zeros(len(self._qresult), dtype=dtype)
        for i, rec in enumerate(self._qresult):
            dataSet[i] = converter(getattr(rec, field.name))
        return dataSet

    def __getitem__(self, name):
        return getattr(self, name)


class XgdsPlotManager(LazyAttributes):
    def __init__(self):
        super(XgdsPlotManager, self).__init__()
        self._models = {}

    def addModel(self, djangoModel, name=None):
        if name is None:
            name = djangoModel.__name__
        plotModel = XgdsPlotModel(djangoModel)
        self._models[name] = plotModel
        setattr(self, name, plotModel)

    def addAlias(self, alias, plotModel, entry=None):
        if entry is None:
            entry = alias
        self.setLazy(alias, lambda: getattr(plotModel, entry))

    def filterTime(self, start=None, end=None):
        for plotModel in self._models.itervalues():
            plotModel.filterTime(start, end)


class XgdsJoinModel(object):
    def __init__(self, seriesList, timeSpacing=None, sparse=True, times=None):
        if timeSpacing is not None:
            timeSpacingDays = float(timeSpacing) / (60 * 60 * 24)

        if times is None:
            times = np.concatenate([s.timestamp.data for s in seriesList])

            # restrict to the intersection of the intervals covered by
            # the various data sets
            minVal = max([s.timestamp.data.min() for s in seriesList])
            maxVal = min([s.timestamp.data.max() for s in seriesList])
            times = times[np.nonzero(np.logical_and(times >= minVal,
                                                    times <= maxVal))]
        times = np.unique(times)

        if sparse:
            if timeSpacing is not None:
                tsLow = np.floor(times / timeSpacingDays)
                tsHigh = tsLow + 1
                times = timeSpacingDays * np.unique(np.concatenate(tsLow, tsHigh))
        else:
            assert timeSpacing is not None
            rngMin = times[0]
            rngMax = times[-1]
            rngMinLow = np.floor(rngMin / timeSpacingDays) * timeSpacingDays
            rngMaxHigh = np.ceil(rngMax / timeSpacingDays) * timeSpacingDays
            times = np.arange(rngMinLow, rngMaxHigh, timeSpacingDays)

        self.seriesList = seriesList
        self.timestamp = XgdsPlotTimeSeries('timestamp',
                                            'Timestamp (%s)' % settings.XGDS_PLOT_TIME_ZONE_NAME,
                                            data=times,
                                            isDate=True)
        self.timeOfDay = XgdsPlotTimeSeries('timeOfDay',
                                            'Time of day (hours, %s)' % settings.XGDS_PLOT_TIME_ZONE_NAME,
                                            data=np.mod(self.timestamp.data, 1) * 24,
                                            timestamp=self.timestamp)

        for s in self.seriesList:
            interpFunc = sp.interpolate.interp1d(s.timestamp.data, s.data, bounds_error=False)
            sdata = interpFunc(self.timestamp.data)
            smasked = np.ma.masked_array(sdata, np.isnan(sdata))
            newSeries = XgdsPlotTimeSeries(s.name,
                                           s.label,
                                           data=smasked,
                                           timestamp=self.timestamp,
                                           timeOfDay=self.timeOfDay,
                                           isDate=s.isDate)
            setattr(self, s.name, newSeries)


def gjoin(seriesList, timeSpacing=None, sparse=True, times=None):
    return XgdsJoinModel(seriesList, timeSpacing, sparse, times)


def setAxisDate(axisName):
    fig = plt.gcf()
    ax = fig.gca()
    if axisName == 'x':
        ax.xaxis_date(tz=pytz.utc)
        selectedAxis = ax.xaxis
    elif axisName == 'y':
        ax.yaxis_date(tz=pytz.utc)
        selectedAxis = ax.yaxis
    loc = matplotlib.dates.AutoDateLocator(interval_multiples=True)
    selectedAxis.set_major_locator(loc)
    fmt = ShortDateFormatter(loc)
    selectedAxis.set_major_formatter(fmt)


def setXAxisDate():
    setAxisDate('x')


def setYAxisDate():
    setAxisDate('y')


def _getArgData(x):
    if isinstance(x, XgdsPlotTimeSeries):
        return x.data
    else:
        return x


def _applyLabel(x, labelFunc):
    if isinstance(x, XgdsPlotTimeSeries):
        label = getattr(x, 'label', None)
        if label:
            labelFunc(label)


def _applyDate(x, dateFunc):
    if isinstance(x, XgdsPlotTimeSeries):
        if x.isDate:
            dateFunc()


def gplot(x, y, *args, **kwargs):
    plt.plot(_getArgData(x), _getArgData(y), *args, **kwargs)
    _applyLabel(x, plt.xlabel)
    _applyLabel(y, plt.ylabel)
    _applyDate(x, setXAxisDate)
    _applyDate(y, setYAxisDate)


def gscatter(x, y, c='b', *args, **kwargs):
    plt.scatter(_getArgData(x), _getArgData(y), c=_getArgData(c),
                *args, **kwargs)
    if isinstance(c, XgdsPlotTimeSeries):
        cb = plt.colorbar()
        _applyLabel(c, lambda label: cb.ax.set_ylabel(label))
    _applyLabel(x, plt.xlabel)
    _applyLabel(y, plt.ylabel)
    _applyDate(x, setXAxisDate)
    _applyDate(y, setYAxisDate)


def gheatmap(x, y, bins=30, **kwargs):
    xdata = _getArgData(x)
    ydata = _getArgData(y)

    # filter out missing values -- histogram2d can't handle them
    anyUndefined = np.logical_or(np.isnan(xdata),
                                 np.isnan(ydata))
    if hasattr(xdata, 'mask'):
        anyUndefined = np.logical_or(anyUndefined, xdata.mask)
    if hasattr(ydata, 'mask'):
        anyUndefined = np.logical_or(anyUndefined, ydata.mask)
    if np.count_nonzero(anyUndefined):
        defined = np.nonzero(np.logical_not(anyUndefined))
        xdata = xdata[defined]
        ydata = ydata[defined]

    heatmap, xedges, yedges = np.histogram2d(xdata,
                                             ydata,
                                             bins=bins)
    heatmap = np.rot90(heatmap)  # histogram2d output is weird
    extent = [xedges[0], xedges[-1], yedges[0], yedges[-1]]
    im = plt.imshow(heatmap, extent=extent, aspect='auto')
    _applyLabel(x, plt.xlabel)
    _applyLabel(y, plt.ylabel)
    _applyDate(x, setXAxisDate)
    _applyDate(y, setYAxisDate)
    cb = plt.colorbar(im)
    cb.ax.set_ylabel('Counts')


def ghist(x, **kwargs):
    xdata = _getArgData(x)

    # filter out missing values
    if np.count_nonzero(np.isnan(xdata)):
        xdata = xdata[np.nonzero(np.logical_not(np.isnan(xdata)))]
    if hasattr(xdata, 'mask') and np.count_nonzero(xdata.mask):
        xdata = xdata[np.nonzero(np.logical_not(xdata.mask))]

    plt.hist(xdata, **kwargs)
    _applyLabel(x, plt.xlabel)
    plt.ylabel('Counts')
