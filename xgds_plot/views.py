# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden, Http404
from django.template import RequestContext

from geocamUtil import anyjson as json
from geocamUtil.loader import getClassByName

from xgds_plot import settings


def setupTimeSeries():
    """
    Process the XGDS_PLOT_TIME_SERIES setting. Normalize and fill in
    default values as needed.
    """
    for series in settings.XGDS_PLOT_TIME_SERIES:
        series.setdefault('queryType', 'xgds_plot.query.Django')
        series.setdefault('valueType', 'xgds_plot.value.Scalar')
        queryClass = getClassByName(series['queryType'])
        queryManager = queryClass(series)
        valueClass = getClassByName(series['valueType'])
        valueManager = valueClass(series, queryManager)

    return settings.XGDS_PLOT_TIME_SERIES

TIME_SERIES = setupTimeSeries()

def dumps(obj):
    return json.dumps(obj, indent=4, sort_keys=True)


def meta(request):
    return HttpResponse(dumps(TIME_SERIES),
                        mimetype='application/json')


def tile(request):
    raise NotImplementedError()


def plots(request):
    exportFields = ('DATA_URL',
                    'SCRIPT_NAME',
                    'XGDS_ZMQ_WEB_SOCKET_URL',)
    exportSettings = dict(((k, getattr(settings, k)) for k in exportFields))
    return render_to_response('xgds_plot/plots.html',
                              {'settings': dumps(exportSettings)},
                              context_instance=RequestContext(request))
