# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

import time

from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden, Http404
from django.template import RequestContext

from geocamUtil import anyjson as json

from xgds_plot.meta import TIME_SERIES
from xgds_plot import settings


def dumps(obj):
    return json.dumps(obj, indent=4, sort_keys=True)


def meta(request):
    return HttpResponse(dumps(TIME_SERIES),
                        mimetype='application/json')


def now(request):
    return HttpResponse(unicode(int(time.time() * 1000)).encode('utf-8'),
                        mimetype='text/plain; charset="utf-8"')

def plots(request):
    exportFields = ('DATA_URL',
                    'XGDS_PLOT_DATA_SUBDIR',
                    'SCRIPT_NAME',
                    'XGDS_ZMQ_WEB_SOCKET_URL',
                    'XGDS_PLOT_LIVE_PLOT_HISTORY_LENGTH_MS',
                    'XGDS_PLOT_SEGMENT_RESOLUTION',
                    'XGDS_PLOT_MIN_DISPLAY_RESOLUTION',
                    )
    exportSettings = dict(((k, getattr(settings, k)) for k in exportFields))
    return render_to_response('xgds_plot/plots.html',
                              {'settings': dumps(exportSettings)},
                              context_instance=RequestContext(request))
