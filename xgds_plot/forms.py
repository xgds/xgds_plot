# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

from django import forms

from xgds_plot import models as plotModels


saveAsNewVersionField = forms.BooleanField(initial=True, label='Save as new version',
                                          help_text='If true, save edited entry as a new record with an incremented version number (recommended during ops, to avoid confusion)')
startIndexingAtCurrentTimeField = forms.BooleanField(initial=True, label='Start indexing at current time',
                                                     help_text='If true, overwrite "Start time" field with current time in UTC; skips indexing historical data (recommended during ops, to ensure live data is indexed in a timely way)')

class TimeSeriesFormWithVersionOption(forms.ModelForm):
    saveAsNewVersion = saveAsNewVersionField
    startIndexingAtCurrentTime = startIndexingAtCurrentTimeField

    class Meta:
        model = plotModels.TimeSeries
