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

import re
import datetime
import collections
import json

from django.db import models

from geocamUtil.TimeUtil import utcDateTimeToPosix


def intIfInt(val):
    """
    Turn a string into an int if it looks like an int.
    """
    if re.search(r'^\d+$', val):
        return int(val)
    else:
        return val


def recursiveUpdate(d, u):
    if isinstance(u, collections.Mapping):
        d = d.copy()
        for k, v in u.iteritems():
            d[k] = recursiveUpdate(d.get(k, {}), v)
        return d
    else:
        return u


class AbstractTimeSeries(models.Model):
    name = models.CharField(max_length=80, blank=True, null=True)
    version = models.PositiveIntegerField(default=1, editable=False,
                                          help_text='Explicit version control. When you edit and save a time series in the admin interface, instead of updating the database record, it will create a new database record with an incremented version number, and initially inactive.')

    active = models.BooleanField(default=True,
                                 help_text='If true, index this time series, making it potentially available for strip charts and maps'
                                 )

    startTime = models.DateTimeField(null=True, blank=True, verbose_name='Start time',
                                     help_text='If specified, only index values after the given UTC time. You may prefer to use the "Start indexing at current time field" at the bottom instead.')
    endTime = models.DateTimeField(null=True, blank=True, verbose_name='End time',
                                   editable=False,  # don't anticipate using this. here if we really need it.
                                   help_text='Only index values before the given UTC time (speeds up processing)')

    stripChartMin = models.FloatField(null=True, blank=True, verbose_name='Strip chart min',
                                      help_text='Minimum value on y axis of strip chart')
    stripChartMax = models.FloatField(null=True, blank=True, verbose_name='Strip chart max',
                                      help_text='Maximum value on y axis of strip chart')
    stripChartSmoothingSigmaSeconds = models.FloatField(null=True, blank=True,
                                                        verbose_name='Strip chart smoothing (seconds)',
                                                        help_text='Sigma value for Gaussian smoothing of strip chart time series (measured in seconds)')
    heatMapMin = models.FloatField(null=True, blank=True,
                                   verbose_name='Heat map min',
                                   help_text='Minimum value in heat map color range (values at this level or below will be colored blue with default colormap).')
    heatMapMax = models.FloatField(null=True, blank=True,
                                   verbose_name='Heat map max',
                                   help_text='Maximum value in heat map color range (values at this level or above will be colored red with default colormap)')
    heatMapSmoothingMeters = models.FloatField(null=True, blank=True,
                                               verbose_name='Heat map smoothing (meters)',
                                               help_text='Sigma value for Gaussian smoothing of heat map (measured in meters)')

    options = models.TextField(blank=True, help_text='Options for plot are built up in following order: (1) getDefaultOptions() from the Django model, (2) overwrite with any values from this options field, (3) overwrite with any values specified above (such as "stripChartMin").')

    class Meta:
        abstract = True
        ordering = ('name', 'version')

    def getValueName(self):
        return '%s v%s' % (self.name, self.version)

    def getValueCode(self):
        return re.sub(' ', '_', self.getValueName().lower())

    def __unicode__(self):
        return self.getValueName()

    @classmethod
    def getDefaultOptions(cls):
        return {
            'type': 'TimeSeries',
            'queryType': 'xgds_plot.query.Django',
            'valueType': 'xgds_plot.value.Scalar',
        }

    def getStartTimePosixMs(self):
        if self.startTime is None:
            return None
        return utcDateTimeToPosix(self.startTime) * 1000

    def getEndTimePosixMs(self):
        if self.endTime is None:
            return None
        return utcDateTimeToPosix(self.endTime) * 1000

    @classmethod
    def getValueFields(cls):
        return (
            ('getValueName', 'valueName'),
            ('getValueCode', 'valueCode'),
            ('getStartTimePosixMs', 'startTime'),
            ('getEndTimePosixMs', 'endTime'),
            ('stripChartMin', 'plotOpts.yaxis.min'),
            ('stripChartMax', 'plotOpts.yaxis.max'),
            ('stripChartSmoothingSigmaSeconds', 'smoothing.sigmaSeconds'),
            ('heatMapMin', 'map.colorRange.0'),
            ('heatMapMax', 'map.colorRange.1'),
            ('heatMapSmoothingMeters', 'map.smoothingMeters'),
        )

    def fillValue(self, opts, fieldName, metaFieldName):
        value = getattr(self, fieldName, None)
        if callable(value):
            value = value()
        if value in (None, ''):
            return
        # import sys; print >> sys.stderr, 'value:', value
        # import sys; print >> sys.stderr, 'opts:', opts

        elts = [intIfInt(val) for val in metaFieldName.split('.')]
        pathToDict = elts[:-1]
        fieldInDict = elts[-1]
        currentDict = opts
        for elt in pathToDict:
            # import sys; print >> sys.stderr, currentDict
            currentDict = currentDict[elt]

        currentDict[fieldInDict] = value

    def fillValues(self, opts):
        """
        Plug field values (e.g. stripChartMin) into the right places in
        the opts dict, according to the correspondence specified in
        getValueFields().
        """
        for fieldName, metaFieldName in self.getValueFields():
            self.fillValue(opts, fieldName, metaFieldName)

    def getOptions(self):
        opts = self.getDefaultOptions()
        # import sys; print >> sys.stderr, 'options:', self.options
        # import sys; print >> sys.stderr, 'options2:', json.loads(self.options)
        if self.options:
            opts = recursiveUpdate(opts, json.loads(self.options))
        self.fillValues(opts)
        return opts

    def preSaveVersionIncrementIfNeeded(self):
        """
        If the user has edited a pre-existing database record and is
        trying to save it, instead of over-writing the old record, we
        want to create a new modified record with an incremented version
        number and set to inactive (active=False,
        quickLookActive=False).

        This function should be called in the ModelAdmin for any models
        derived from this class. See xgds_plot/admin.py for an example.
        """
        if self.pk is not None:
            self.pk = None
            self.version += 1
            self.active = False
            self.quickLookActive = False


class TimeSeries(AbstractTimeSeries):
    pass
