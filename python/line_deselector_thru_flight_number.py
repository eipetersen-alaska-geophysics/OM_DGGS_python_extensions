################## LINE DESELECTOR ####################################################
"""
Author: Eric Petersen
Date: 2025-06-11

DESCRIPTION:
Deselect lines in open geodatabase through user input of the flight # through which to
deselect lines.

##################### UPDATE 2025-06-23 by Eric Petersen ##################### 
Based off feedback from Phuong Vo (Geological Society of Canada):
-----------------------------------------------------------------
"I had to add the following lines 

import numpy as np           
if not hasattr(np, 'float'): 
    np.float = float         
if not hasattr(np, 'int'):   
    np.int = int

at the beginning of the script to be compatible with newer NumPy versions (v1.20+), 
where np.float and np.int are deprecated or removed. This compatibility patch prevents 
crashes if legacy code or libraries still try to use those names.  Eric’s python script 
does not include this patch, so if it (or any of its dependencies) tries to use np.float 
or np.int while running under version(s) NumPy 1.20 or newer, it may crash with an 
AttributeError."
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

