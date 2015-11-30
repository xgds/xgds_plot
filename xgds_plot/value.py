#__BEGIN_LICENSE__
# Copyright (c) 2015, United States Government, as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All rights reserved.
#
# The xGDS platform is licensed under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0.
#
# Unless required by applicable law or agreed to in writing, software distributed
# under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
# CONDITIONS OF ANY KIND, either express or implied. See the License for the
# specific language governing permissions and limitations under the License.
#__END_LICENSE__

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
