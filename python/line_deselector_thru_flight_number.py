################## LINE DESELECTOR ####################################################
"""
Author: Eric Petersen
Date: 2025-06-11

DESCRIPTION:
Deselect lines in open geodatabase through user input of the flight # through which to
deselect lines.
"""

import geosoft.gxapi as gxapi
import geosoft.gxpy as gxpy
import geosoft.gxpy.gdb as gxdb
import geosoft.gxpy.project as gxproj

################## ACTUAL SCRIPT THAT RUNS IN OM MENU ####################################################
def rungx():
    gxp = gxpy.gx.gx()

 ################## SELECT OPEN DATABASE ####################################################
    gdb = gxdb.Geosoft_gdb.open() # Select currently open geodatabase.
    if gdb is None: # If no open gdb, return error:
        gxapi.GXSYS.display_message("GX", "No database open.")
        return
    
    # Get user input on flights to exclude:
    max_flt_ex = gxproj.get_user_input(title='Deselect Survey Lines From Flight 1 Through Flight #',
                                    prompt ='Flight #:',
                                    kind='int')

    ################### WORK THROUGH EACH LINE: ####################################################
    for line in gdb.list_lines():
        # Retrieve flight number:
        FLIGHT, fid = gdb.read_channel(line, 'FLIGHT')
        flight_num = FLIGHT[0]
        if flight_num <= max_flt_ex: # See if it's within the flights you want to exclude.
            gdb.select_lines(line, select=False)
    
    gxapi.GXSYS.display_message("Lines Deselected!","Done.")

