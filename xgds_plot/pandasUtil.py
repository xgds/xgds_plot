# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

import logging
import sys
from itertools import izip
import copy

import numpy as np
import pandas as pd
import pandas.io.sql as psql
import MySQLdb
from django.conf import settings
from django.db.models import get_app, get_models
from matplotlib import pyplot as plt

import isruApp
import isruApp.models

_djangoDbSettings = settings.DATABASES['default']
DB_SETTINGS = dict(host=_djangoDbSettings['HOST'],
                   port=int(_djangoDbSettings['PORT']),
                   user=_djangoDbSettings['USER'],
                   passwd=_djangoDbSettings['PASSWORD'],
                   db=_djangoDbSettings['NAME'])
dbConnectionG = None


def getDbConnection():
    global dbConnectionG
    if not dbConnectionG:
        dbConnectionG = MySQLdb.connect(**DB_SETTINGS)
    return dbConnectionG


def quoteIfString(obj):
    if isinstance(obj, (str, unicode)):
        return '"%s"' % obj
    else:
        return obj


class DjangoDataFrame(object):
    def __init__(self, model):
        self.name = model.__name__
        self.qset = model.objects.all()

    def _replaceQset(self, qset):
        result = copy.copy(self)
        result.qset = qset
        return result

    def getSql(self):
        # str(self.qset.query) usually works but quoting seems to be
        # messed up if you have a string parameter.
        query, params = self.qset.query.sql_with_params()
        params = tuple([quoteIfString(obj) for obj in params])
        return query % params

    def filter(self, *args, **kwargs):
        return self._replaceQset(self.qset.filter(*args, **kwargs))

    def __getitem__(self, k):
        return self._replaceQset(self.qset[k])

    def getFrame(self, *args, **kwargs):
        filtered = self.filter(*args, **kwargs)
        sql = filtered.getSql()
        logging.debug('getFrame: %s', sql)
        result = psql.frame_query(sql, con=getDbConnection())
        return self.postProcess(result)

    def getRecord(self, *args, **kwargs):
        frame = self.getFrame(*args, **kwargs)
        if len(frame) != 1:
            raise ValueError('getRecord() query returned %s matches, expected exactly 1'
                             % len(frame))
        return frame.xs(0)

    def postProcess(self, result):
        return result


class Data(object):
    def addModel(self, model, name=None):
        if name is None:
            name = model.name
        setattr(self, name, model)

    def __str__(self):
        models = sorted(vars(self).keys())
        return '\n'.join(models)

    def __repr__(self):
        return str(self)


def rejectOutliers(frame, fieldName,
                   percent=1,
                   rejectLow=True,
                   rejectHigh=True):
    field = getattr(frame, fieldName)
    lo, hi = np.percentile(field, [percent, 100 - percent])
    filter = True
    if rejectLow:
        filter = np.logical_and(filter, lo <= field)
    if rejectHigh:
        filter = np.logical_and(filter, field <= hi)
    return frame[filter]

# monkey patch
pd.DataFrame.rejectOutliers = rejectOutliers


def _applyLabel(x, labelFunc):
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
