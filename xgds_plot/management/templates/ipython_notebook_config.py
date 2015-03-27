# __BEGIN_LICENSE__
#Copyright © 2015, United States Government, as represented by the 
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

"""
ipython_notebook_config.py is a place for you to put site-specific
settings for the IPython Notebook. Settings made here override whatever
is specified in shared_notebook_config.py.

This file must not be checked into version control!
"""

# pylint: disable=E0602

# load shared settings from shared_notebook_config.py in this directory
load_subconfig('shared_notebook_config.py')

######################################################################
# Add your modifications below this point

# Uncomment the section below for a production setup. It will turn on
# password authentication, and tweak things to support proxied
# connections coming in through Apache.

# c = get_config()

# One password for all users. To generate a password hash to use here,
# run the following:
#   from IPython.lib import passwd
#   passwd('your_password')
#   [copy and paste output into the line below]

# c.NotebookApp.password = u'... fill in output of passwd() method ...'

# The Tornado server rejects "cross-origin" requests by default, for
# security reasons. In our standard setup, the 'Origin' header in the
# request from Apache to Tornado is 'https://yoursite.xgds.org', but
# the request goes to Tornado over HTTP (HTTP != HTTPS), so we use the
# 'allow_origin_pat' workaround (implemented in the iPython Notebook
# code) to tell Tornado either protocol is ok.  See discussion at
# https://github.com/ipython/ipython/issues/5525 .

# c.NotebookApp.allow_origin_pat = 'https?://yoursite.xgds.org'

# *Or* you can use this line to totally turn off Tornado's cross-origin
# check.

# c.NotebookApp.allow_origin = '*'  # ... at own risk
