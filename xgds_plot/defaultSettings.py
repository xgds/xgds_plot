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

# pylint: disable=W0105

XGDS_ZMQ_WEB_SOCKET_URL = 'ws://{{host}}:8001/zmq/'

# include trailing slash but no leading slash
XGDS_PLOT_DATA_SUBDIR = 'xgds_plot/'

# the shortest time interval between data points
XGDS_PLOT_MIN_DATA_INTERVAL_MS = 500

# the longest time interval that might need to be displayed in a plot
XGDS_PLOT_MAX_SEGMENT_LENGTH_MS = 365 * 24 * 60 * 60 * 1000

# the number of data points in a segment
XGDS_PLOT_SEGMENT_RESOLUTION = 512

# if min display resolution is N, the segment level will be set to
# load and display at least N data points (and might be up to 2N)
XGDS_PLOT_MIN_DISPLAY_RESOLUTION = 384

# make segment files more readable for debugging (increases file size)
XGDS_PLOT_PRETTY_PRINT_JSON_SEGMENTS = False

# in live mode, display this much history by default
XGDS_PLOT_LIVE_PLOT_HISTORY_LENGTH_MS = 2 * 60 * 1000

# In live mode, keep the right hand side of the strip chart this far
# ahead of the current time (according to the xGDS server). Setting
# this to a non-zero amount can avoid an issue where new data appears
# out of bounds to the right of the display time interval if the clock
# on the data source is ahead of the clock on the xGDS server.
XGDS_PLOT_LIVE_PLOT_FUTURE_TIME_MS = 20 * 1000

# whether to start in live mode by default when plots screen is opened
XGDS_PLOT_LIVE_MODE_DEFAULT = True

# when no new data is coming in, constantly checking for new data is wasteful
XGDS_PLOT_CHECK_FOR_NEW_DATA = True

XGDS_PLOT_MAP_TILE_EPS = 1e-9
XGDS_PLOT_MAP_PIXELS_PER_TILE = 256
XGDS_PLOT_MAP_BBOX = [-155.470761, 19.756284,
                      -155.463084, 19.763668]

# map layers broken up by day, split at midnight in the specified time zone.
# if 'auto', use Django settings.TIME_ZONE.
XGDS_PLOT_OPS_TIME_ZONE = 'UTC'

# zoom in interval [MIN_ZOOM, MAX_ZOOM)
XGDS_PLOT_MAP_ZOOM_RANGE = (14, 22)

# batch sleep avoids overloading server; larger values sleep more
XGDS_PLOT_BATCH_SLEEP_TIME_FACTOR = 3

# Specifies which time series are available for plotting. See example below.
XGDS_PLOT_TIME_SERIES = {}

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

# xgds_plot assumes its input data is in the UTC time zone and
# produces its indexes with UTC timestamps. this offset allows you to
# change the time zone for the plot and profile display only.
XGDS_PLOT_TIME_OFFSET_HOURS = 0
XGDS_PLOT_TIME_ZONE_NAME = 'UTC'

XGDS_PLOT_PROFILES = ()

XGDS_PLOT_PROFILE_TIME_GRID_RESOLUTION = 256
XGDS_PLOT_PROFILE_Z_RANGE = (0, 10, 1.0)
XGDS_PLOT_PROFILE_EXPORT_TIME_RESOLUTION_SECONDS = 30 * 60

XGDS_PLOT_PROFILE_TIME_PIX_RESOLUTION = 1400
XGDS_PLOT_PROFILE_Z_PIX_RESOLUTION = 200

# list any extra ipython notebook startup files here. they will be installed in
# <site>/var/notebook/profile_default/startup
XGDS_PLOT_NOTEBOOK_STARTUP_FILES = []

XGDS_PLOT_GET_DATES_FUNCTION = 'geocamTrack.trackUtil.getDatesWithPositionData'

# include this in your siteSettings.py BOWER_INSTALLED_APPS
XGDS_PLOT_BOWER_INSTALLED_APPS = ('flot',
                                  )
