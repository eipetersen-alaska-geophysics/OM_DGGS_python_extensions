################## LINE SELECTOR ####################################################
"""
Author: Eric Petersen
Date: 2025-06-24

Copyright (C) 2025 Eric Petersen
This program is free software: you can redistribute it and/or modify it under the terms of the 
GNU General Public License as published by the Free Software Foundation, either version 3 of the 
License, or (at your option) any later version. This program is distributed in the hope that it 
will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY 
or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details, 
<http://www.gnu.org/licenses/>.

DESCRIPTION:
Select lines in open geodatabase through user input of the flight # through which to
select lines. Modified from the line_deselector tool.
-----------------------------------------------------------------
"""

import geosoft.gxapi as gxapi
import geosoft.gxpy as gxpy
import geosoft.gxpy.gdb as gxdb
import geosoft.gxpy.project as gxproj
import numpy as np

################## ACTUAL SCRIPT THAT RUNS IN OM MENU ####################################################
def rungx():
    # Patch to define np.float and np.int, fixing deprecated numpy functionality used by
    #    some Oasis montaj tools:
    if not hasattr(np, 'float'): 
        np.float = float         
    if not hasattr(np, 'int'):   
        np.int = int

    gxp = gxpy.gx.gx() # Set current instance of gxp

 ################## SELECT OPEN DATABASE ####################################################
    gdb = gxdb.Geosoft_gdb.open() # Select currently open geodatabase.
    if gdb is None: # If no open gdb, return error:
        gxapi.GXSYS.display_message("GX", "No database open.")
        return
    
    # Get user input on flights to exclude:
    max_flt_ex = gxproj.get_user_input(title='Select Survey Lines From Flight 1 Through Flight #',
                                    prompt ='Flight #',
                                    kind='int',
                                    items=['Start','End'])

    ################### WORK THROUGH EACH LINE: ####################################################
    for line in gdb.list_lines():
        # Retrieve flight number:
        FLIGHT, fid = gdb.read_channel(line, 'FLIGHT')
        flight_num = FLIGHT[0]
        if flight_num <= max_flt_ex: # See if it's within the flights you want to exclude.
            gdb.select_lines(line, select=True)
    
    gxapi.GXSYS.display_message("Lines Selected!","Done.")

