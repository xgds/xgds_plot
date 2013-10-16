# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

import os
import shutil
import sys
import datetime
import re

from geocamUtil import anyjson as json

from xgds_plot import settings

FLOAT_REGEX = re.compile(r'^-?\d+(\.\d*)?$')

# CompactFloat/compactFloats: annoying hack to avoid printing out bogus
# extra digits when floats are embedded in JSON objects.
# http://stackoverflow.com/questions/1447287/format-floats-with-standard-json-module


class CompactFloat(float):
    def __repr__(self):
        return '%.15g' % self


def compactFloats(obj):
    if isinstance(obj, float):
        return CompactFloat(obj)
    elif isinstance(obj, dict):
        return {k: compactFloats(v) for k, v in obj.iteritems()}
    elif isinstance(obj, (list, tuple)):
        return [compactFloats(o) for o in obj]
    return obj


def rmIfPossible(path):
    print '  deleting %s' % path
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.unlink(path)
    except OSError, oe:
        print >> sys.stderr, 'Failed to remove %s: %s' % (path, oe)


class JsonStore(object):
    def __init__(self, path):
        self.path = os.path.realpath(path)

    def write(self, obj):
        pathDir = os.path.dirname(self.path)
        if not os.path.exists(pathDir):
            os.makedirs(pathDir)
        json.dump(obj, open(self.path, 'wb'), indent=4, sort_keys=True)

    def read(self, dflt=None):
        if os.path.exists(self.path):
            return json.load(open(self.path, 'rb'))
        else:
            return dflt


def parseTime(timeString, offset=None):
    if offset is None:
        offset = datetime.timedelta(hours=settings.XGDS_PLOT_TIME_OFFSET_HOURS)

    # exact match 'now'
    now = datetime.datetime.utcnow()
    if timeString == 'now':
        return now

    # match a float
    m = FLOAT_REGEX.search(timeString)
    if m:
        f = float(timeString)
        if f < 1e+6:
            # interpret small values as delta hours from now
            dt = datetime.timedelta(hours=f)
            return now + dt
        else:
            # interpret large values as Java-style millisecond epoch time
            return datetime.datetime.utcfromtimestamp(f * 1e-3)

    # parse a couple of full date formats. interpreted as times in the display
    # time zone.
    try:
        return datetime.datetime.strptime(timeString, '%Y-%m-%d %H:%M') - offset
    except ValueError:
        pass

    try:
        return datetime.datetime.strptime(timeString, '%Y-%m-%d %H:%M:%S') - offset
    except ValueError:
        pass

    raise ValueError('unrecognized time string "%s"' % timeString)
