# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

XGDS_ZMQ_WEB_SOCKET_URL = 'ws://{{host}}:8001/zmq/'

# Specifies which time series are available for plotting. See example below.
XGDS_PLOT_TIME_SERIES = ()

"""

There are four types of time series meta-data records, in the following
'inheritance hierarchy':

 * TimeSeriesMeta
   * Group
   * TimeSeries
   * IncludeMeta
   * IncludeFunctionResultMeta

Ignoring the IncludeX types for the moment, the XGDS_PLOT_TIME_SERIES
object is organized as a tree whose internal nodes are Groups and whose
leaves are TimeSeries. The top-level XGDS_PLOT_TIME_SERIES object must
be a Group.

The IncludeX types provide a way to include more time series meta-data
specified in other Python modules. IncludeX objects are evaluated and
interpolated into the tree structure at startup time, so at run-time the
tree contains only Group and TimeSeries objects. (The fully evaluated
tree is also what gets passed to the JavaScript client side.)

IncludeX objects must be contained in the 'members' list of a Group
object. Each IncludeX object must evaluate to a TimeSeriesMetaList, that
is, an iterable of TimeSeriesMeta objects, which is interpolated into
the members list.

Each IncludeX object has a 'name' field which is a fully-qualified
Python identifier, including the module name. Each IncludeMeta object
evaluates to the value of its 'name' identifier. Each
IncludeFunctionResultMeta object treats the value of its 'name'
identifier as a Python callable and evaluates to the result of invoking
the callable. Evaluation is recursive, so IncludeX results can include
other IncludeX objects.

XGDS_PLOT_TIME_SERIES = {
    'type': 'Group',
    'name': 'All',
    'members': [
        {
            'type': 'TimeSeries',
            'valueField': 'snScalar',
            'queryModel': 'isruApp.resolvenstier1data',
            'queryTimestampField': 'timestampSeconds',
            'show': True,
        },
        {
            'type': 'IncludeFunctionResultMeta',
            'name': 'isruApp.views.getNirvsBandDepths',
        },
        {
            'type': 'IncludeMeta',
            'name': 'isruApp.settings.ROVER_PARAMETER_TIME_SERIES',
        },
    ]
}

"""
