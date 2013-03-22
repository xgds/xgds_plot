# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

"""
ipython_notebook_config.py is a place for you to put site-specific
settings for the IPython Notebook. Settings made here override whatever
is specified in shared_notebook_config.py.

This file must not be checked into version control!
"""

# load shared settings from shared_notebook_config.py in this directory
load_subconfig('shared_notebook_config.py')

######################################################################
# Add your modifications below this point

# uncomment the section below to switch to https protocol on port
# 8443. you'll need to generate your own SSL certificate.

#from IPython.lib import passwd as hashPassword
#from xgds_plot import settings

#c.NotebookApp.ip = '*'
#c.NotebookApp.port = 8443
#c.NotebookApp.certfile = settings.VAR_ROOT + 'notebook/profile_default/security/cert.pem'
#c.NotebookApp.password = hashPassword('...')
