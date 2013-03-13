# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

import logging
import sys
from itertools import izip

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


def getOrderField(field):
    if field.startswith('-'):
        field = field[1:] + ' DESC'
    return field


def getOrderFields(ordering):
    return ', '.join((getOrderField(field) for field in ordering))


def sqlAnd(*constraints):
    return ' AND '.join(constraints)


def sqlOr(*constraints):
    return ' OR '.join(constraints)


def getData(query='',
            select=True,
            table=None,
            fields='*',
            where=None,
            order=True,
            ordering=None,
            limit=None,
            con=None):
    if con is None:
        con = getDbConnection()

    if select and table is not None:
        selectClause = 'SELECT %s FROM %s ' % (fields, table)
        query = selectClause + query

    if where is not None:
        whereClause = ' WHERE %s' % where
        query += whereClause

    if order and ordering is not None:
        orderClause = ' ORDER BY %s' % getOrderFields(ordering)
        query += orderClause

    if limit is not None:
        limitClause = ' LIMIT %s' % limit
        query += limitClause

    logging.info('getData: %s' % query)
    return psql.frame_query(query, con=con)


class DataModel(object):
    def __init__(self, model, **kwargs):
        self.con = kwargs.pop('con', None)
        self.name = model.__name__

        kwargs.setdefault('table', model._meta.db_table)
        if model._meta.ordering:
            kwargs.setdefault('ordering', model._meta.ordering)

        self.defaults = kwargs

    def all(self):
        return self.filter()

    def filter(self, *args, **kwargs):
        for k, v in self.defaults.iteritems():
            kwargs.setdefault(k, v)
        result = getData(*args, **kwargs)
        return self.postprocess(result, *args, **kwargs)

    def postprocess(self, result, *args, **kwargs):
        if (hasattr(result, 'timestampSeconds')
            and hasattr(result, 'timestampMicroseconds')):
            ts = pd.Series(np.array(result.timestampSeconds,
                                    dtype='datetime64[us]')
                           + np.array(result.timestampMicroseconds,
                                      dtype='timedelta64[us]'),
                           name='timestamp',
                           index=result.index)
            result = result.join(ts)
            result = result.drop(['timestampSeconds',
                                  'timestampMicroseconds'],
                                 axis=1)

        if hasattr(result, 'timestamp'):
            result.index = result.timestamp

        return result

    def get(self, *args, **kwargs):
        matches = self.filter(*args, **kwargs)
        if len(matches) != 1:
            raise ValueError('get() query returned %s matches, expected exactly 1'
                             % len(matches))
        return matches.xs(0)


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
