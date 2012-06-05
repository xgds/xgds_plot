# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

XGDS_ZMQ_WEB_SOCKET_URL = '{{host}}:8001/zmq'

# A list of data sets available for plotting.
XGDS_PLOT_TIME_SERIES = (

    {
        'code': 'nsRatio',
        'name': 'Neutron Spectrometer Sn/Cd Ratio',
        'query': {
            'type': 'xgds_plot.query.Django',
            'model': 'isruApp.NSTelemetry',
            'timestamp': 'timestamp',
        },
        'value': {
            'type': 'xgds_plot.value.Ratio',
            'fields': ('sn', 'cd'),
        },
        'rasterMap': {
            'type': 'xgds_plot.rasterMap.Basic',
            'colorRange': [2.9, 3.2],
        }
    },

    {
        'code': 'nsSn',
        'name': 'Neutron Spectrometer Sn (counts/s)',
        'query': {
            'type': 'django',
            'model': 'isruApp.NSTelemetry',
            'timestamp': 'timestamp',
        },
        'value': {
            'type': 'xgds_plot.value.Scalar',
            'fields': 'sn',
        },
        'rasterMap': {
            'type': 'isruApp.nsRasterMap.NsSnMap',
            'colorRange': [42, 48],
        },
    },

    {
        'code': 'nsCd',
        'name': 'Neutron Spectrometer Cd (counts/s)',
        'colorRange': [42, 48],
    },

)

# A list of functions that return meta-data for additional time series.
# For example, you might specify a function that retrieves a list of
# available time series from a database table.
XGDS_PLOT_TIME_SERIES_GENERATORS = (
    # 'mymodule.myfunction'
)
