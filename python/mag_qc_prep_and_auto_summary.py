################## MAGNETIC QC PREP CALCULATIONS AND AUTO SUMMARY ####################################################
"""
Author: Eric Petersen
Date: 2025-06-11

DESCRIPTION:
This python extension for Oasis montaj is designed to work on a geodatabase with standard
DGGS channel naming schema. It calculates new channels necessary for QC work on production
magnetic data, supporting QC of:
    - Flightline altitude, deviation from the drape surface defined in the TOS
    - Diurnal mag variability (solar storms)
    - Magnetic noise (4th difference)

This extension was translated from a .gs script previously used by Abraham et al., and 
derived from the Geological Society of Canada (GSC)'s standard magnetic QC procedures.
Original scripts can be found here:
\\morta.dnr.state.ak.us\geophysics\projects\magnetic_qc_working\gs\
Example script: NRGmag_qc_prep_script_20hz_4th_lp96_hp80_clip0p1.gs

The following changes were made following the translation of the script to the python extension:
    - Low pass / high pass filter feature not implemented (this feature may be added in the future)
    - Speed calculation generalized so that extension is valid for data of different sampling frequencies.
    - Auto detection capability added for identifying out-of-spec lines/line segments.

AUTO DETECTION CAPABILITY:
The extension automatically identifies lines and line segments which are out of specification in the following way:
    - DRAPE SURFACE: Line segments more than 15 meters over or under the drape surface for more than 800 m 
        consecutive meters along track.
    - DIURNAL: Lines where diurnal mag measurements differ from the 15 second or 60 second chords by 0.5 nT or 3 nT 
        respectively.
    - NOISE: Lines where the 4th difference value of MAGCOM exceeds +/-0.01 nT/m4
When the extension is completed running, the summary text box will display the number of lines that are out of spec (OOS)
    for each of these categories.
Summary files recording more details will be put into %project_folder%/QC_auto_summaries/. Only categories for
    which OOS lines have been identified will be saved here. The following information will be saved to those files:
    - "OOS_drape" : a record/row for each OOS segment recording Flight #, Line #, Segment Fiducial Start, 
        Segment Fiducial End, Length OOS (out of spec), Max deviation from the drape surface, Avg. deviation from the
        drape surface.
    - "OOS_diurnal": a record/row for each OOS line displaying Line # and Number of records/data points OOS for that line.
    - "OOS_4th_difference": a record/row for each OOS line displaying Line # and Number of records/data points OOS 
        for that line.

After running this extension, DGGS QC dbviews can then be loaded for continuing standard QC practice.
    The auto-detection summary files can be used to guide that process and as a second check against human
    error in manual QC work.

POTENTIAL FUTURE WORK/UPDATES:
    - Implement low pass / high pass filter, including user inputs.
    - Implement new magHFnoise_v2.2 filter from GSC.
    - Implement user input for .gdb to run extension on (maybe not necessary).
    - Implement user input for location to output auto summary files (maybe not necessary).
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

def interpolate_array(arr):
    """Interpolate an array linearly."""
    not_nans = ~np.isnan(arr)
    x = np.arange(len(arr))
    return np.interp(x, x[not_nans], arr[not_nans], left=np.nan, right=np.nan)

def shift_right(arr, shift_number=1):
    """ Shift values in array for diff/speed calcs. Default to shift right +1."""
    shifted = np.empty_like(arr, dtype=float)
    shifted[shift_number:] = arr[:-shift_number]
    shifted[:shift_number] = np.nan
    return shifted

def auto_drape_analysis(flight, line, flt_alt, drape, step_dist, fid, ztol=15, dtol=800):
    """
    Function to automatically identify sections of the flight which are out of spec for drape.
    Inputs, with the exception of flight, line, ztol, & dtol, are expected to be numpy arrays derived
        from .gdb channels for a given survey line. They should all be the same length.
    Inputs:
        flight = flight number, single value
        line = line number, single value
        flt_alt = survey flight altitude, m
        drape = drape surface, m
        step_dist = step distance along flight track, m
        fid = survey fiducial
        ztol = vertical drape tolerance, default 15 m 
        dtol = along track distance tolerance, default 800 m
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
        OOS_drape_mask = mask of where the flight is out of spec of the drape.
    """
    # Prepare results dataframe
    results = pd.DataFrame(columns=['Flight', 'Line', 'Fid_start','Fid_end','Length_OOS','Max_drape_dev','Avg_drape_dev'])

    # Calculate drape deviations and define out-of-spec (OOS) records
    drape_deviance = flt_alt - drape # raw drape deviance
    OOS_drape = ((drape_deviance > ztol) | (drape_deviance < -ztol)) #index for flight over or under drape tolerance
    OOS_drape_mask = OOS_drape.astype('int8')

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
        if seg_distance < dtol: # disregard if segment is shorter than dtol (default 800 m)
            OOS_drape_mask[seg_start:seg_end] = 0
            continue
        else: 
            num_segs += 1 # Keep count number of OOS segments
            # Extreme value (max for positive, min for negative)
            if np.sign(drape_deviance[seg_start]) == 1:
                extrema = np.nanmax(drape_deviance[seg_start:seg_end])
            elif np.sign(drape_deviance[seg_start]) == -1:
                extrema = np.nanmin(drape_deviance[seg_start:seg_end])
            # Record results
            results.loc[len(results)] = [flight, line, fid[seg_start], fid[seg_end], seg_distance, extrema, np.nanmean(drape_deviance[seg_start:seg_end])]
    
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
    out_path_noise = out_path + '/OOS_4th_difference.csv'
    out_path_diurnal = out_path + '/OOS_diurnal.csv'
    out_path_drape = out_path + '/OOS_drape.csv'
    # Pandas dataframes for storing summary values:
    noise_summary = pd.DataFrame(columns=['Line','OOS_Count'])
    diurnal_summary = pd.DataFrame(columns=['Line', 'OOS_Count_15chord', 'OOS_Count_60chord'])
    drape_summary = pd.DataFrame(columns=['Flight', 'Line', 'Fid_start','Fid_end','Length_OOS','Max_drape_dev','Avg_drape_dev'])

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

    # Diurnal Chord Analysis:
    chrd_Lmag15_channel = add_channel(gdb, "chrd_Lmag15")
    chrd_Lmag60_channel = add_channel(gdb, "chrd_LmagD60")
    L_magDIFF15_channel = add_channel(gdb, "L_magDIFF15")
    L_magDIFF60_channel = add_channel(gdb, "L_magDIFF60")

    # Speed and Drape Analysis:
    drape_p15_channel = add_channel(gdb, "drape_p15") # Drape plus 15 m
    drape_m15_channel = add_channel(gdb, "drape_m15") # Drape minus 15 m
    speed_channel = add_channel(gdb, "speed") # Speed
    step_distance_channel = add_channel(gdb, "step_distance") # Speed
    drape_OOS_channel = add_channel(gdb, "drape_OOS_mask", dtype='int8') # Drape out-of-spec mask

    # Noise channels:
    MAGCOM_2nd_channel = add_channel(gdb, "MAGCOM_2nd") # 2nd difference
    MAGCOM_4th_channel = add_channel(gdb, "MAGCOM_4th") # 4th difference

    # Constant Value Channels:
    p_3_channel = add_channel(gdb, "p_3") # Positive 3.0 (for comparison to 60 second chord)
    m_3_channel = add_channel(gdb, "m_3") # Negative 3.0 (for comparison to 60 second chord)
    p_0p5_channel = add_channel(gdb, "p_0p5") # Positive 0.5 (for comparison to 15 second chord)
    m_0p5_channel = add_channel(gdb, "m_0p5") # Negative 0.5 (for comparison to 15 second chord)
    p_0p05_channel = add_channel(gdb, "p_0p05") # Positive 0.05 (for comparison to low-pass/high-pass channel)
    m_0p05_channel = add_channel(gdb, "m_0p05") # Negative 0.05 (for comparison to low-pass/high-pass channel)
    p_0p01_channel = add_channel(gdb, "p_0p01") # Positive 0.01 (for comparison to 4th diff channel)
    m_0p01_channel = add_channel(gdb, "m_0p01") # Negative 0.01 (for comparison to 4th diff channel)
    zero_channel = add_channel(gdb, "zero") # Zero

    # Set Counters for Lines out of spec (OOS):
    OOS_4th_line_count = 0
    OOS_diurnal_line_count = 0
    ################### WORK THROUGH EACH LINE: ####################################################
    for line in gdb.list_lines():
        # Retrieve data in array format for channel math:
        UTCTIME, fid = gdb.read_channel(line, 'UTCTIME')
        DIURNAL, fid = gdb.read_channel(line, 'DIURNAL')
        EASTING, fid = gdb.read_channel(line, 'EASTING')
        NORTHING, fid = gdb.read_channel(line, 'NORTHING')
        SURFACE, fid = gdb.read_channel(line, 'SURFACE')
        MAGCOM, fid = gdb.read_channel(line, 'MAGCOM')
        GPSALT, fid = gdb.read_channel(line, 'GPSALT')
        FLIGHT, fid = gdb.read_channel(line, 'FLIGHT')
        FIDCOUNT, fid = gdb.read_channel(line, 'FIDCOUNT')
        flight_num = FLIGHT[0]

        ################ CONSTANT VALUE ARRAYS AND CHANNELS FOR PLOTTING/ANALYSIS #########################
        dummy = np.full_like(DIURNAL, np.nan, dtype=float) # To be used for infilling with dummy values.
        ones = np.full_like(DIURNAL, 1, dtype=float) # To be used for infilling with constant values.
        gdb.write_channel(line, p_3_channel, ones*3, fid) # Positive 3
        gdb.write_channel(line, m_3_channel, ones*-3, fid) # Negative 3
        gdb.write_channel(line, p_0p5_channel, ones*0.5, fid) # Positive 0.5
        gdb.write_channel(line, m_0p5_channel, ones*-0.5, fid) # Negative 0.5
        gdb.write_channel(line, p_0p05_channel, ones*0.05, fid) # Positive 0.05
        gdb.write_channel(line, m_0p05_channel, ones*-0.05, fid) # Negative 0.05
        gdb.write_channel(line, p_0p01_channel, ones*0.01, fid) # Positive 0.01
        gdb.write_channel(line, m_0p01_channel, ones*-0.01, fid) # Negative 0.01
        gdb.write_channel(line, zero_channel, ones*0, fid) # Zeros

        ################ DIURNAL QC FOR 15 SECOND CHORD #########################
        # Calculate L_magD_15
        cond = (np.floor(UTCTIME / 15 ) * 15 ) == (np.floor(UTCTIME * 10)/10)
        L_magD_15_values = np.where(cond, DIURNAL, dummy) # Values of L_magD only every 15 seconds.
        # Calculate chrd_Lmag15
        chrd_Lmag15_values = interpolate_array(L_magD_15_values) # Interpolate between each 15 second value to produce the chord.
        gdb.write_channel(line, chrd_Lmag15_channel, chrd_Lmag15_values, fid) # Write chord to the gdb
        # Calculate L_magDIFF15
        L_magDIFF15_values = DIURNAL - chrd_Lmag15_values # Calculate the difference
        gdb.write_channel(line, L_magDIFF15_channel, L_magDIFF15_values, fid) # Write the DIFF to the gdb
        OOS_15 = sum ( (np.abs(L_magDIFF15_values) > 0.5)) # Number of data points for which 15 sec Diurnal chord is out-of-spec.

        ################ DIURNAL QC FOR 60 SECOND CHORD #########################
        # Calculate L_magD_60
        cond = (np.floor(UTCTIME / 60 ) * 60 ) == (np.floor(UTCTIME * 10)/10)
        L_magD_60_values = np.where(cond, DIURNAL, dummy) # Values of L_magD only every 60 seconds.
        # Calculate chrd_Lmag60
        chrd_Lmag60_values = interpolate_array(L_magD_60_values) # Interpolate between each 60 second value to produce the chord.
        gdb.write_channel(line, chrd_Lmag60_channel, chrd_Lmag60_values, fid) # Write chord to the gdb
        # Calculate L_magDIFF60
        L_magDIFF60_values = DIURNAL - chrd_Lmag60_values # Calculate the difference
        gdb.write_channel(line, L_magDIFF60_channel, L_magDIFF60_values, fid) # Write the DIFF to the gdb
        OOS_60 = sum ( (np.abs(L_magDIFF15_values) > 3)) # Number of data points for which 60 sec Diurnal chord is out-of-spec.

        # Record out-of-spec summary for diurnals:
        if OOS_15 > 0 or OOS_60 > 0:
            OOS_diurnal_line_count += 1 # add to the line count.
            diurnal_summary.loc[len(diurnal_summary)] = [line, OOS_15, OOS_60]

        ################ DRAPE AND SPEED QC #########################
        gdb.write_channel(line, drape_p15_channel, SURFACE+15, fid) # Drape surface plus 15 m
        gdb.write_channel(line, drape_m15_channel, SURFACE-15, fid) # Drape surface minus 15 m
        # Calculate Speed:
        # Note that in calling UTCTIME to calculate speed instead of hard-coding the data frequency that this script is agnostic/generalized 
        #           to data recorded in different Hz.
        step_distance = np.sqrt( (shift_right(EASTING) - EASTING)**2 + (shift_right(NORTHING) - NORTHING)**2 )
        speed_values = step_distance / (UTCTIME - shift_right(UTCTIME))
        gdb.write_channel(line, step_distance_channel, step_distance, fid) # Write step distance values to gdb.
        gdb.write_channel(line, speed_channel, speed_values, fid) # Write speed values to gdb.

        # Detect and record out-of-spec segments for drape:
        OOS_drape, OOS_drape_mask = auto_drape_analysis(flight_num, line, GPSALT, SURFACE, step_distance, FIDCOUNT) # calling function defined above
        gdb.write_channel(line, drape_OOS_channel, OOS_drape_mask, fid) # Write the drape OOS mask to the gdb.
        if OOS_drape is not None:
            drape_summary = pd.concat([drape_summary, OOS_drape], ignore_index=True) # add OOS drape segments to summary dataframe

        ################ NOISE QC #########################
        MAG_4th_diff = np.diff(MAGCOM, n=4) # 4th difference values
        gdb.write_channel(line, MAGCOM_2nd_channel, np.diff(MAGCOM, n=2), fid) # save 2nd difference to gdb
        gdb.write_channel(line, MAGCOM_4th_channel, MAG_4th_diff, fid) # save 4th difference to gdb
        # Identify if there is OOS 4th difference on this line:
        OOS_4th = sum ( (np.abs(MAG_4th_diff) > 0.01)) # Number of data points for which 4th difference noise out-of-spec.
        if OOS_4th>0: # If any out of spec records.
            OOS_4th_line_count += 1 # add a line to the count!
            noise_summary.loc[len(noise_summary)] = [line, OOS_4th] # Append the line to the noise_summary.

    ################ SAVE SUMMARY FILES #########################
    # Noise summary
    if OOS_4th_line_count > 0: # save only if any lines out-of-spec.
        noise_summary.to_csv(out_path_noise, index=False)
    # Diurnal summary
    if OOS_diurnal_line_count > 0: # save only if any lines out-of-spec.
        diurnal_summary.to_csv(out_path_diurnal, index=False)
    # Drape summary
    OOS_drape_segment_count = len(drape_summary)
    OOS_drape_line_count = len(drape_summary['Line'].unique())
    OOS_drape_meters = np.sum(drape_summary['Length_OOS'])
    if OOS_drape_segment_count > 0:
        drape_summary.to_csv(out_path_drape, float_format="%.0f", index=False)

    sum_text = "{} lines ({} segments, {:.1f} line-km total) with drape out of spec. \n {} lines with diurnal out of spec. \n {} lines with potential noise problems. \n\n Summary files saved to {} \n\n Please move summary files to appropriate archive directory.".format(OOS_drape_line_count, OOS_drape_segment_count, OOS_drape_meters/1000, OOS_diurnal_line_count, OOS_4th_line_count, out_path)

    gxapi.GXSYS.display_message("QC Calculations Complete.", sum_text)

if __name__ == "__main__":
    gxpy.gx.GXpy()
    rungx()