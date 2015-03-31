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

import operator

from geocamUtil.loader import getClassByName

from xgds_plot import settings


def expandTimeSeriesMeta(meta):
    """
    Evaluates IncludeMeta and IncludeFunctionResultMeta objects. Returns
    a list of trees with Group and TimeSeries nodes.
    """
    mtype = meta['type']
    if mtype == 'Group':
        lists = [expandTimeSeriesMeta(m)
                 for m in meta['members']]
        return [{'type': 'Group',
                 'members': reduce(operator.add, lists, [])}]
    elif mtype == 'TimeSeries':
        return [meta.copy()]
    elif mtype == 'IncludeMeta':
        return [expandTimeSeriesMeta(m)
                for m in getClassByName(meta['name'])]
    elif mtype == 'IncludeFunctionResultMeta':
        func = getClassByName(meta['name'])
        return reduce(operator.add,
                      [expandTimeSeriesMeta(m)
                       for m in func()],
                      [])
    else:
        raise ValueError('expandTimeSeriesMeta: unknown meta type %s'
                         % mtype)


def flattenTimeSeriesMeta(group):
    """
    Turns a tree of Group and TimeSeries into a flattened list of
    TimeSeries objects.
    """
    members = group['members']
    result = []
    for meta in members:
        mtype = meta['type']
        if mtype == 'Group':
            result += flattenTimeSeriesMeta(meta)
        elif mtype == 'TimeSeries':
            result.append(meta)
        else:
            raise ValueError('flattenTimeSeriesMeta: unknown meta type %s'
                             % mtype)
    return result


def setupTimeSeries():
    """
    Process the XGDS_PLOT_TIME_SERIES setting. Normalize and fill in
    default values as needed.
    """
    if not settings.XGDS_PLOT_TIME_SERIES:
        return []

    tree = expandTimeSeriesMeta(settings.XGDS_PLOT_TIME_SERIES)[0]
    metaList = flattenTimeSeriesMeta(tree)
    for series in metaList:
        series.setdefault('queryType', 'xgds_plot.query.Django')
        series.setdefault('valueType', 'xgds_plot.value.Scalar')
        queryClass = getClassByName(series['queryType'])
        queryManager = queryClass(series)
        valueClass = getClassByName(series['valueType'])
        _valueManager = valueClass(series, queryManager)

    return metaList

TIME_SERIES = setupTimeSeries()
TIME_SERIES_LOOKUP = dict([(_m['valueCode'], _m)
                           for _m in TIME_SERIES])
