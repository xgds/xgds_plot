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

from django import forms

from xgds_plot import models as plotModels


saveAsNewVersionField = forms.BooleanField(initial=True, label='Save as new version', required=False,
                                          help_text='If true, save edited entry as a new record with an incremented version number (recommended during ops, to avoid confusion)')
startIndexingAtCurrentTimeField = forms.BooleanField(initial=True, label='Start indexing at current time', required=False,
                                                     help_text='If true, overwrite "Start time" field with current time in UTC; skips indexing historical data (recommended during ops, to ensure live data is indexed in a timely way)')

class TimeSeriesFormWithVersionOption(forms.ModelForm):
    saveAsNewVersion = saveAsNewVersionField
    startIndexingAtCurrentTime = startIndexingAtCurrentTimeField

    class Meta:
        model = plotModels.TimeSeries
        fields = '__all__'  # TODO not sure if we want to include all fields
