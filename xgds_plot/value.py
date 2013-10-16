# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

from xgds_plot.segment import ScalarSegment, RatioSegment
from xgds_plot.tile import ScalarTile, RatioTile


class Scalar(object):
    makeSegment = ScalarSegment
    makeTile = ScalarTile

    def __init__(self, meta, queryManager):
        self.valueField = meta['valueField']
        self.queryManager = queryManager

        # normalize meta-data
        if 'valueCode' not in meta:
            meta['valueCode'] = self.valueField
        if 'valueName' not in meta:
            meta['valueName'] = self.queryManager.getValueName(meta['valueField'])

    def getValue(self, rec):
        return getattr(rec, self.valueField)


class Ratio(object):
    makeSegment = RatioSegment
    makeTile = RatioTile

    def __init__(self, meta, queryManager):
        self.numField, self.denomField = meta['valueFields']
        self.queryManager = queryManager

    def getValue(self, rec):
        return (getattr(rec, self.numField),
                getattr(rec, self.denomField))
