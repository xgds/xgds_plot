# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

import time
import operator

from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden, Http404
from django.template import RequestContext

from geocamUtil import anyjson as json
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

def dumps(obj):
    return json.dumps(obj, indent=4, sort_keys=True)


def meta(request):
    return HttpResponse(dumps(TIME_SERIES),
                        mimetype='application/json')


def now(request):
    return HttpResponse(unicode(int(time.time() * 1000)).encode('utf-8'),
                        mimetype='text/plain; charset="utf-8"')

def tile(request):
    raise NotImplementedError()


def plots(request):
    exportFields = ('DATA_URL',
                    'SCRIPT_NAME',
                    'XGDS_ZMQ_WEB_SOCKET_URL',
                    'XGDS_PLOT_LIVE_PLOT_HISTORY_LENGTH_MS',
                    )
    exportSettings = dict(((k, getattr(settings, k)) for k in exportFields))
    return render_to_response('xgds_plot/plots.html',
                              {'settings': dumps(exportSettings)},
                              context_instance=RequestContext(request))
