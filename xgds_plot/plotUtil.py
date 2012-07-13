# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

import os
import shutil
import sys

from geocamUtil import anyjson as json

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
        return dict((k, compactFloats(v)) for k, v in obj.items())
    elif isinstance(obj, (list, tuple)):
        return map(compactFloats, obj)
    return obj


def rmIfPossible(path):
    print '  deleting %s' % path
    try:
        shutil.rmtree(path)
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
