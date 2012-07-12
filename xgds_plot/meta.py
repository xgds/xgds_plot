
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
        return [expandTimeSeriesMeta(m)
                for m in func()]
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
    tree = expandTimeSeriesMeta(settings.XGDS_PLOT_TIME_SERIES)[0]
    metaList = flattenTimeSeriesMeta(tree)
    for series in metaList:
        series.setdefault('queryType', 'xgds_plot.query.Django')
        series.setdefault('valueType', 'xgds_plot.value.Scalar')
        queryClass = getClassByName(series['queryType'])
        queryManager = queryClass(series)
        valueClass = getClassByName(series['valueType'])
        valueManager = valueClass(series, queryManager)

    return metaList

TIME_SERIES = setupTimeSeries()
TIME_SERIES_LOOKUP = dict([(m['valueCode'], m)
                           for m in TIME_SERIES])