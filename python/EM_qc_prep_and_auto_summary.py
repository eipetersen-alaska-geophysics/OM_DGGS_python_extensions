################## ELECTROMAGNETIC QC PREP CALCULATIONS AND AUTO SUMMARY ####################################################
"""
Author: Eric Petersen
Date: 2025-07-29

Copyright (C) 2025 Eric Petersen
This program is free software: you can redistribute it and/or modify it under the terms of the 
GNU General Public License as published by the Free Software Foundation, either version 3 of the 
License, or (at your option) any later version. This program is distributed in the hope that it 
will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY 
or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details, 
<http://www.gnu.org/licenses/>.

DESCRIPTION:
This python extension for Oasis montaj is designed to work on a geodatabase with standard
DGGS channel naming schema. It calculates new channels necessary for QC work on production
magnetic data, supporting QC of:
    - Flightline altitude, deviation from the drape surface defined in the TOS

This extension was initiated from a previous extension written by Eric Petersen for 
magnetic QC.

AUTO DETECTION CAPABILITY:
The extension automatically identifies lines and line segments which are out of specification in the following way:
    - DRAPE SURFACE: Line segments more than 20 meters over or under the "do not exceed"surface for more than 1200 m 
        consecutive meters along track.
When the extension is completed running, the summary text box will display the number of lines that are out of spec (OOS)
    for each of these categories.
Summary files recording more details will be put into %project_folder%/QC_auto_summaries/. Only categories for
    which OOS lines have been identified will be saved here. The following information will be saved to those files:
    - "OOS_drape" : a record/row for each OOS segment recording Flight #, Line #, Segment Fiducial Start, 
        Segment Fiducial End, Length OOS (out of spec), Max deviation from the drape surface, Avg. deviation from the
        drape surface.
"""

import numpy as np
import pandas as pd
import os
import geosoft.gxapi as gxapi
import geosoft.gxpy as gxpy
import geosoft.gxpy.gdb as gxdb
import geosoft.gxpy.utility as gxutil
import geosoft.gxpy.project as gxproj

################## FUNCTIONS USED BY SCRIPT ####################################################

def add_channel(gdb, name, dtype="float"):
    """Create a new channel with standard properties. Datatype float."""
    if name not in gdb.list_channels():
        return gxdb.Channel.new(gdb, name, dtype=dtype)
    else:
        return gxdb.Channel(gdb, name) # If channel already exists then return it as an object.

def shift_right(arr, shift_number=1):
    """ Shift values in array for diff/speed calcs. Default to shift right +1."""
    shifted = np.empty_like(arr, dtype=float)
    shifted[shift_number:] = arr[:-shift_number]
    shifted[:shift_number] = np.nan
    return shifted

def auto_clearance_analysis(flight, line, drape_deviance, step_dist, speed, fid, ztol=20, dtol=1200):
    """
    Function to automatically identify sections of the flight which are out of spec for clearance in 
        the context of EM.
    NOTE that this is different from analyzing drape in the context of Magnetic data, as in this case
        we are only flagging EXCEEDANCES of the "do-not-exceed" surface, as opposed to deviations from
        the drape surface, positive or negative.
    Inputs, with the exception of flight, line, ztol, & dtol, are expected to be numpy arrays derived
        from .gdb channels for a given survey line. They should all be the same length.
    Inputs:
        flight = flight number, single value
        line = line number, single value
        flt_alt = survey flight altitude, m
        drape_deviance = drape surface, m
        step_dist = step distance along flight track, m
        fid = survey fiducial
        ztol = vertical drape tolerance, default 20 m 
        dtol = along track distance tolerance, default 1200 m
    Outputs:
        results = dataframe with a row for each OOS segment of length greater than dtol.
            contains the following fields:
                flight
                line
                fid_start
                fid_end
                length_OOS
                max_drape_dev (maximum deviance from drape tolerance)
                avg_drape_dev (average deviance from drape tolerance)
                avg_speed (average speed during the OOS segment)
        OOS_drape_mask = mask of where the flight is out of spec of the drape.
    """
    # Prepare results dataframe
    results = pd.DataFrame(columns=['Flight', 'Line', 'Fid_start','Fid_end','Length_OOS','Max_drape_dev','Avg_drape_dev','Avg_speed'])

    # Raise value error if flt_alt, drape, step_dist, speed, fid not all the same length.
    if not len(drape_deviance) == len(step_dist) == len(speed) == len(fid):
        raise ValueError("Channel arrays for auto drape analysis are not all the same length.")

    # Calculate drape deviations and define out-of-spec (OOS) records
    OOS_drape = (drape_deviance > ztol) #index for flight over drape tolerance
    OOS_drape_mask = OOS_drape.astype('int8') # OOS drape mask to prep for saving in channel

    #gxapi.GXSYS.display_message("Debugging.... OOS_drape_mask", "{}".format(OOS_drape_mask))
    
    # Find starts and ends to continuous segments of OOS_drape:
    d = np.diff(OOS_drape.astype(int))
    seg_starts = np.where(d==1)[0] + 1 # +1 because diff shifts by 1
    seg_ends = np.where(d==-1)[0] + 1
    # Edge case: starts at beginning
    if OOS_drape[0]:
        seg_starts = np.r_[0, seg_starts]
    # Edge case: ends at end
    if OOS_drape[-1]:
        seg_ends = np.r_[seg_ends, len(OOS_drape)-1]

    # Go through each segment:
    num_segs = 0 # counter for number of segments recorded out of spec
    for seg_start, seg_end in zip(seg_starts, seg_ends):
        seg_distance = np.nansum(step_dist[seg_start:seg_end]) # calculate total distance along segment
        if seg_distance < dtol: # disregard if segment is shorter than dtol (default 1200 m)
            OOS_drape_mask[seg_start:seg_end] = 0 # OOS drape mask to prep for saving in channel; remove the segment if < 1200 m
            continue
        else: 
            num_segs += 1 # Keep count number of OOS segments
            # Extreme value (max for positive, min for negative)
            if np.sign(drape_deviance[seg_start]) == 1:
                extrema = np.nanmax(drape_deviance[seg_start:seg_end])
            elif np.sign(drape_deviance[seg_start]) == -1:
                extrema = np.nanmin(drape_deviance[seg_start:seg_end])
                OOS_drape_mask[seg_start:seg_end] = -1
            # Record results
            if len(fid) > max(seg_start, seg_end): # Make sure that the segment indices are in bounds for the channel value arrays.
                results.loc[len(results)] = [flight, line, fid[seg_start], fid[seg_end], seg_distance, extrema, np.nanmean(drape_deviance[seg_start:seg_end]), np.nanmean(speed[seg_start:seg_end])]
            else:
                raise ValueError("Segment indices are out-of-bounds for channel value arrays.")
    
    # Return results
    if num_segs > 0:
        return results, OOS_drape_mask
    else:
        return None, OOS_drape_mask

################## ACTUAL SCRIPT THAT RUNS IN OM MENU ####################################################
def rungx():
    gxp = gxpy.gx.gx()

    ################## QC Summaries Prep ####################################################
    # Out path for QC Summaries
    out_path = gxutil.folder_workspace() + 'QC_auto_summaries\\' # Workspace/project folder + QC_auto_summaries.
    if out_path:
        os.makedirs(out_path, exist_ok=True)
    # Prep output file paths
    out_path_drape = out_path + '/OOS_drape.csv'
    # Pandas dataframes for storing summary values:
    drape_summary = pd.DataFrame(columns=['Flight', 'Line', 'Fid_start','Fid_end','Length_OOS','Max_drape_dev','Avg_drape_dev','Avg_speed'])

    ################## SELECT DATABASE ####################################################
    # Prompt user to select database, default to current if any
    #db_path = gxapi.GXEDB.user_select("Select a database", "GDB", "", "")
    #db_path = gxproj.get_user_input(title='Select GDB to Perform QC Prep On',
     #                               prompt ='GBD:',
      #                              kind='file',
       #                             filemask='*.grd')
    db_path = None
    if not db_path: # Select currently open geodatabase.
        gdb = gxdb.Geosoft_gdb.open()
        if gdb is None:
            gxapi.GXSYS.display_message("GX", "No database selected or open.")
            return
    else:
        gdb = gxdb.Geosoft_gdb.open(db_path)

    # Select all lines
    gdb.select_lines(gdb.list_lines())

    ################### ADD CHANNELS ####################################################

    # Speed and Drape Analysis:
    drape_p20_channel = add_channel(gdb, "drape_p20") # Drape plus 15 m
#    drape_m15_channel = add_channel(gdb, "drape_m15") # Drape minus 15 m
    speed_channel = add_channel(gdb, "speed") # Speed
    step_distance_channel = add_channel(gdb, "step_distance") # Step distance
    drape_deviation_channel = add_channel(gdb, "drape_deviation") # Flight altitude deviation from drape.
    drape_OOS_channel = add_channel(gdb, "drape_OOS_mask", dtype='int8') # Drape out-of-spec mask

    ################### WORK THROUGH EACH LINE: ####################################################
    for line in gdb.list_lines():
        # Retrieve data in array format for channel math:
        UTCTIME, fid = gdb.read_channel(line, 'UTCTIME')
        EASTING, fid = gdb.read_channel(line, 'EASTING')
        NORTHING, fid = gdb.read_channel(line, 'NORTHING')
        SURFACE, fid = gdb.read_channel(line, 'SURFACE')
        GPSALT, fid = gdb.read_channel(line, 'GPSALT')
        FLIGHT, fid = gdb.read_channel(line, 'FLIGHT')
        FIDCOUNT, fid = gdb.read_channel(line, 'FIDCOUNT')
        flight_num = FLIGHT[0]

        ################ DRAPE AND SPEED QC #########################
        gdb.write_channel(line, drape_p20_channel, SURFACE+20, fid) # Drape surface plus 15 m
        #gdb.write_channel(line, drape_m15_channel, SURFACE-15, fid) # Drape surface minus 15 m
        # Calculate Speed:
        # Note that in calling UTCTIME to calculate speed instead of hard-coding the data frequency that this script is agnostic/generalized 
        #           to data recorded in different Hz.
        step_distance = np.sqrt( (shift_right(EASTING) - EASTING)**2 + (shift_right(NORTHING) - NORTHING)**2 )
        speed_values = step_distance / (UTCTIME - shift_right(UTCTIME))
        drape_deviation = GPSALT - SURFACE # deviation from drape
        gdb.write_channel(line, drape_deviation_channel, drape_deviation, fid) # Write drape deviation values to gdb.
        gdb.write_channel(line, step_distance_channel, step_distance, fid) # Write step distance values to gdb.
        gdb.write_channel(line, speed_channel, speed_values, fid) # Write speed values to gdb.

        # Detect and record out-of-spec segments for drape:
        OOS_drape, OOS_drape_mask = auto_clearance_analysis(flight_num, line, drape_deviation, step_distance, speed_values, FIDCOUNT) # calling function defined above
        gdb.write_channel(line, drape_OOS_channel, OOS_drape_mask, fid) # Write the drape OOS mask to the gdb.
        if OOS_drape is not None:
            drape_summary = pd.concat([drape_summary, OOS_drape], ignore_index=True) # add OOS drape segments to summary dataframe

    ################ SAVE SUMMARY FILES #########################
    # Drape summary
    OOS_drape_segment_count = len(drape_summary)
    OOS_drape_line_count = len(drape_summary['Line'].unique())
    OOS_drape_meters = np.sum(drape_summary['Length_OOS'])
    if OOS_drape_segment_count > 0:
        drape_summary.to_csv(out_path_drape, float_format="%.0f", index=False)

    sum_text = "{} lines ({} segments, {:.1f} line-km total) with flight height out of spec. \n\n Summary files saved to {} \n\n Please move summary files to appropriate archive directory.".format(OOS_drape_line_count, OOS_drape_segment_count, OOS_drape_meters/1000, out_path)

    gxapi.GXSYS.display_message("QC Calculations Complete.", sum_text)

if __name__ == "__main__":
    gxpy.gx.GXpy()
    rungx()