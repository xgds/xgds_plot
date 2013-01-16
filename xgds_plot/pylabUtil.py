#!/usr/bin/env python
# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

import numpy as np
import pytz
import matplotlib.dates
import django.db.models

from xgds_plot.plotUtil import *


class ShortDateFormatter(matplotlib.dates.AutoDateFormatter):
    def __call__(self, x, pos=0):
        scale = float( self._locator._get_unit() )

        d = matplotlib.dates.DateFormatter
        if ( scale >= 365.0 ):
            self._formatter = d("%Y", self._tz)
        elif ( scale == 30.0 ):
            self._formatter = d("%b %Y", self._tz)
        elif ( (scale == 1.0) or (scale == 7.0) ):
            self._formatter = d("%b %d", self._tz)
        elif ( scale == (1.0/24.0) ):
            self._formatter = d("%H:%M", self._tz)
        elif ( scale == (1.0/(24*60)) ):
            self._formatter = d("%H:%M", self._tz)
        elif ( scale == (1.0/(24*3600)) ):
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


class PlotDataSet(object):
    def __init__(self, qset):
        self._qset = list(qset)
        assert self._qset
        self._n = len(self._qset)
        self._fields = {}
        for fieldTuple in self._qset[0]._meta._field_cache:
            field = fieldTuple[0]
            self._fields[field.name] = field
        self._cache = {}

    @staticmethod
    def getDataType(field):
        if isinstance(field, django.db.models.FloatField):
            return (np.float64, lambda val: val)
        if isinstance(field, (django.db.models.IntegerField,
                              django.db.models.PositiveIntegerField,
                              django.db.models.AutoField)):
            return (np.int64, lambda val: val)
        elif isinstance(field, django.db.models.DateTimeField):
            return (np.float64, matplotlib.dates.date2num)
        else:
            return (np.float64, lambda val: val)

    def __getattr__(self, name):
        assert name in self._fields
        dtype, converter = self.getDataType(self._fields[name])
        dataSet = np.zeros(self._n, dtype=dtype)
        for i, rec in enumerate(self._qset):
            dataSet[i] = converter(getattr(rec, name))

        setattr(self, name, dataSet)
        return dataSet

    def __getitem__(self, name):
        return getattr(self, name)
