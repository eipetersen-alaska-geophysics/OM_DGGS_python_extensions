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
    - NOISE: Lines where the 4th difference value of MAGCOM exceeds +/-0.01 nT
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

##################### UPDATE 2025-06-18 by Eric Petersen #####################
    - Fixed OOS determination for diurnal 60 second chord (was erroneously referencing 15 second chord in this calculation)
    - Added OOS masks as new channels for Diurnal OOS (15 and 60 second chords separately), 4th Difference OOS. Previously
        had OOS mask for drape only.
    - Added average speed as an output for the segment summary file for drape OOS.
    - Added flight number to OOS diurnal and noise outputs.

##################### UPDATE 2025-06-23 by Eric Petersen #####################
Based off feedback from Phuong Vo (Geological Society of Canada):
-----------------------------------------------------------------
"With the python script “mag_qc_prep_and_auto_summary.py”, I had to add some additional lines in red checking point to see 
if the input arrays are empty.

def interpolate_array(arr):
    ""Interpolate an array linearly.""
    not_nans = ~np.isnan(arr)                                                #Line 74
    if np.sum(not_nans) == 0:
        # No valid data to interpolate from, return all NaNs of same length
        return np.full_like(arr, np.nan, dtype=float)
    x = np.arange(len(arr))
    return np.interp(x, x[not_nans], arr[not_nans], left=np.nan, right=np.nan)

Without this check, the interpolation function would attempt to operate on empty arrays when arr contains only NaNs, 
leading to a runtime error.

Also I added the following conditional to prevent out-of-bounds errors when slicing or accessing segments from the arrays.
In "auto_drape_analysis" function:

            # Record results                             # Line 149
        if len(fid) > max(seg_start, seg_end) and len(flt_alt) > max(seg_start, seg_end) and len(step_dist) > max(seg_start, seg_end):
            results.loc[len(results)] = [flight, line, fid[seg_start], fid[seg_end], seg_distance, extrema, np.nanmean(drape_deviance[seg_start:seg_end])]"
-------------------------------------------------------------------
I (Eric) also added a check in the "auto_drape_analysis" function to make sure that all the channel value arrays for
the line being analyzed are the same length. If they are not, an error is thrown. They should all be the same length
if called from within the geosoft extension.

##################### UPDATE 2025-06-26 by Eric Petersen #####################
Was previously calculating 4th difference using np.diff(data, n=4); updated to use
the proper symmetric 4th difference formula used by GSC for airborne magnetic QC.
Comparing this to the numpy calculation I find that the results are essentially exactly
the same; they are just shifted in their indices. However we do want to use the 
properly documented/industry standard formula!
"""

import numpy as np
import pandas as pd
import os
import click

################## FUNCTIONS USED BY SCRIPT ####################################################

def add_channel(gdb, name, dtype="float"):
    """Create a new channel with standard properties. Datatype float."""
    if name not in gdb.columns:
        gdb[name] = pd.Series(dtype=dtype)
    return gdb[name]

def interpolate_array(arr):
    """Interpolate an array linearly."""
    not_nans = ~np.isnan(arr)
    if np.sum(not_nans) == 0:
        # If no valid data to interpolate from, return all NaNs of same length
        return np.full_like(arr, np.nan, dtype=float)
    x = np.arange(len(arr))
    return np.interp(x, x[not_nans], arr[not_nans], left=np.nan, right=np.nan)

def shift_right(arr, shift_number=1):
    """ Shift values in array for diff/speed calcs. Default to shift right +1."""
    shifted = np.empty_like(arr, dtype=float)
    shifted[shift_number:] = arr[:-shift_number]
    shifted[:shift_number] = np.nan
    return shifted

def fourth_difference(data):
    """ Calculate fourth difference filter an an array of data"""

    if len(data) < 5:
        raise ValueError("Data array must contain at least 5 points for 4th difference.")
    
    # Calculate 4th difference
    diff4 = (            # M_delta4_i
        data[0:-4]       # M_{i-2}
        - 4 * data[1:-3] # -4 * M_{i-1}
        + 6 * data[2:-2] # +6 * M_{i}
        - 4 * data[3:-1] # -4 * M_{i+1}
        + data[4:]       # + M_{i+2}
    )
    
    # Pad with NaNs at start and end
    diff4_padded = np.full_like(data, np.nan, dtype=float)
    diff4_padded[2:-2] = diff4
    
    return diff4_padded

def auto_drape_analysis(flight, line, drape_deviance, step_dist, speed, fid, ztol=15, dtol=800):
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
                avg_speed (average speed during the OOS segment)
        OOS_drape_mask = mask of where the flight is out of spec of the drape.
    """
    # Prepare results dataframe
    results = pd.DataFrame(columns=['Flight', 'Line', 'Fid_start','Fid_end','Length_OOS','Max_drape_dev','Avg_drape_dev','Avg_speed'])

    # Raise value error if flt_alt, drape, step_dist, speed, fid not all the same length.
    if not len(drape_deviance) == len(step_dist) == len(speed) == len(fid):
        raise ValueError("Channel arrays for auto drape analysis are not all the same length.")

    # Calculate drape deviations and define out-of-spec (OOS) records
    OOS_drape = ((drape_deviance > ztol) | (drape_deviance < -ztol)) #index for flight over or under drape tolerance
    OOS_drape_mask = OOS_drape.astype('int8') # OOS drape mask to prep for saving in channel

    #print("Debugging.... OOS_drape_mask", "{}".format(OOS_drape_mask))
    
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
            OOS_drape_mask[seg_start:seg_end] = 0 # OOS drape mask to prep for saving in channel; remove the segment if < 800 m
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


def process_all(pipeline, data, 
                diurnal_15chord_OOS_threshold = 0.5, # OOS threshold for diurnal 15 second chord
                diurnal_60chord_OOS_threshold = 3, # OOS threshold for diurnal 60 second chord
                MAG_4th_diff_OOS_threshold = 0.05, # OOS threshold for MAG 4th difference. TOS specifies "Noise must be limited to 0.1 nT, peak to peak." +/-0.05 nT threshold as easy way to try to catch that.
                ):
    gdb = data.data
    
    ################## QC Summaries Prep ####################################################                
    # Pandas dataframes for storing summary values:
    noise_summary = pd.DataFrame(columns=['Flight', 'Line','OOS_Count'])
    diurnal_summary = pd.DataFrame(columns=['Flight', 'Line', 'OOS_Count_15chord', 'OOS_Count_60chord'])
    drape_summary = pd.DataFrame(columns=['Flight', 'Line', 'Fid_start','Fid_end','Length_OOS','Max_drape_dev','Avg_drape_dev','Avg_speed'])

    ################### ADD CHANNELS ####################################################

    # Diurnal Chord Analysis:
    chrd_Lmag15_channel = add_channel(gdb, "chrd_Lmag15")
    chrd_Lmag60_channel = add_channel(gdb, "chrd_LmagD60")
    L_magDIFF15_channel = add_channel(gdb, "L_magDIFF15")
    L_magDIFF60_channel = add_channel(gdb, "L_magDIFF60")
    diurnal_15chord_OOS_channel = add_channel(gdb, "diurnal_15chord_OOS_mask", dtype='int8') # Diurnal 15 second chord out-of-spec mask
    diurnal_60chord_OOS_channel = add_channel(gdb, "diurnal_60chord_OOS_mask", dtype='int8') # Diurnal 60 second chord out-of-spec mask

    # Speed and Drape Analysis:
    drape_p15_channel = add_channel(gdb, "drape_p15") # Drape plus 15 m
    drape_m15_channel = add_channel(gdb, "drape_m15") # Drape minus 15 m
    speed_channel = add_channel(gdb, "speed") # Speed
    step_distance_channel = add_channel(gdb, "step_distance") # Step distance
    drape_deviation_channel = add_channel(gdb, "drape_deviation") # Flight altitude deviation from drape.
    drape_OOS_channel = add_channel(gdb, "drape_OOS_mask", dtype='int8') # Drape out-of-spec mask

    # Noise channels:
    MAGCOM_2nd_channel = add_channel(gdb, "MAGCOM_2nd") # 2nd difference
    MAGCOM_4th_channel = add_channel(gdb, "MAGCOM_4th") # 4th difference
    mag_4th_diff_OOS_channel = add_channel(gdb, "mag_4th_diff_OOS_mask", dtype='int8') # 4th difference out-of-spec mask

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
    for line in gdb.index.get_level_values('Line').unique():
        # Retrieve data in array format for channel math:
        UTCTIME = gdb.loc[line, 'UTCTIME'].values
        DIURNAL = gdb.loc[line, 'Diurnal'].values
        EASTING = gdb.loc[line, 'Easting'].values
        NORTHING = gdb.loc[line, 'Northing'].values
        SURFACE = gdb.loc[line, 'Surface'].values
        MAGCOM = gdb.loc[line, 'MAGCOM'].values
        GPSALT = gdb.loc[line, 'GPSALT'].values
        FLIGHT = gdb.loc[line, 'Flight'].values
        FIDCOUNT = gdb.loc[line].index.get_level_values('FIDCOUNT').values
        flight_num = FLIGHT[0]

        ################ CONSTANT VALUE ARRAYS AND CHANNELS FOR PLOTTING/ANALYSIS #########################
        dummy = np.full_like(DIURNAL, np.nan, dtype=float) # To be used for infilling with dummy values.
        ones = np.full_like(DIURNAL, 1, dtype=float) # To be used for infilling with constant values.
        
        gdb.loc[line, "p_3"] = ones*3 # Positive 3
        gdb.loc[line, "m_3"] = ones*-3 # Negative 3
        gdb.loc[line, "p_0p5"] = ones*0.5 # Positive 0.5
        gdb.loc[line, "m_0p5"] = ones*-0.5 # Negative 0.5
        gdb.loc[line, "p_0p05"] = ones*0.05 # Positive 0.05
        gdb.loc[line, "m_0p05"] = ones*-0.05 # Negative 0.05
        gdb.loc[line, "p_0p01"] = ones*0.01 # Positive 0.01
        gdb.loc[line, "m_0p01"] = ones*-0.01 # Negative 0.01
        gdb.loc[line, "zero"] = ones*0 # Zeros

        ################ DIURNAL QC FOR 15 SECOND CHORD #########################
        # Calculate L_magD_15
        cond = (np.floor(UTCTIME / 15 ) * 15 ) == (np.floor(UTCTIME * 10)/10)
        L_magD_15_values = np.where(cond, DIURNAL, dummy) # Values of L_magD only every 15 seconds.
        # Calculate chrd_Lmag15
        chrd_Lmag15_values = interpolate_array(L_magD_15_values) # Interpolate between each 15 second value to produce the chord.
        gdb.loc[line, "chrd_Lmag15"] = chrd_Lmag15_values # Write chord to the gdb
        # Calculate L_magDIFF15
        L_magDIFF15_values = DIURNAL - chrd_Lmag15_values # Calculate the difference
        gdb.loc[line, "L_magDIFF15"] = L_magDIFF15_values # Write the DIFF to the gdb
        OOS_15_mask = (np.abs(L_magDIFF15_values) > diurnal_15chord_OOS_threshold)
        OOS_15 = sum ( OOS_15_mask) # Number of data points for which 15 sec Diurnal chord is out-of-spec.
        gdb.loc[line, "diurnal_15chord_OOS"] = OOS_15_mask.astype('int8') # Write the OOS mask to gdb

        ################ DIURNAL QC FOR 60 SECOND CHORD #########################
        # Calculate L_magD_60
        cond = (np.floor(UTCTIME / 60 ) * 60 ) == (np.floor(UTCTIME * 10)/10)
        L_magD_60_values = np.where(cond, DIURNAL, dummy) # Values of L_magD only every 60 seconds.
        # Calculate chrd_Lmag60
        chrd_Lmag60_values = interpolate_array(L_magD_60_values) # Interpolate between each 60 second value to produce the chord.
        gdb.loc[line, "chrd_Lmag60"] = chrd_Lmag60_values # Write chord to the gdb
        # Calculate L_magDIFF60
        L_magDIFF60_values = DIURNAL - chrd_Lmag60_values # Calculate the difference
        gdb.loc[line, "L_magDIFF60"] = L_magDIFF60_values # Write the DIFF to the gdb
        OOS_60_mask = (np.abs(L_magDIFF60_values) > diurnal_60chord_OOS_threshold) # Mask for where 60 sec diurnal is out-of-spec
        OOS_60 = sum ( OOS_60_mask) # Number of data points for which 60 sec Diurnal chord is out-of-spec. .astype('int8')
        gdb.loc[line, "diurnal_60chord_OOS"] = OOS_60_mask.astype('int8') # Write the OOS mask to gdb

        # Record out-of-spec summary for diurnals:
        if OOS_15 > 0 or OOS_60 > 0:
            OOS_diurnal_line_count += 1 # add to the line count.
            diurnal_summary.loc[len(diurnal_summary)] = [flight_num, line, OOS_15, OOS_60]

        ################ DRAPE AND SPEED QC #########################
        gdb.loc[line, "drape_p15"] = SURFACE+15 # Drape surface plus 15 m
        gdb.loc[line, "drape_m15"] = SURFACE-15 # Drape surface minus 15 m
        # Calculate Speed:
        # Note that in calling UTCTIME to calculate speed instead of hard-coding the data frequency that this script is agnostic/generalized 
        #           to data recorded in different Hz.
        step_distance = np.sqrt( (shift_right(EASTING) - EASTING)**2 + (shift_right(NORTHING) - NORTHING)**2 )
        speed_values = step_distance / (UTCTIME - shift_right(UTCTIME))
        drape_deviation = GPSALT - SURFACE # deviation from drape
        gdb.loc[line, "drape_deviation"] = drape_deviation # Write drape deviation values to gdb.
        gdb.loc[line, "step_distance"] = step_distance # Write step distance values to gdb.
        gdb.loc[line, "speed"] = speed_values # Write speed values to gdb.

        # Detect and record out-of-spec segments for drape:
        OOS_drape, OOS_drape_mask = auto_drape_analysis(flight_num, line, drape_deviation, step_distance, speed_values, FIDCOUNT) # calling function defined above
        gdb.loc[line, "drape_OOS"] = OOS_drape_mask # Write the drape OOS mask to the gdb.
        if OOS_drape is not None:
            drape_summary = pd.concat([drape_summary, OOS_drape], ignore_index=True) # add OOS drape segments to summary dataframe

        ################ NOISE QC #########################
        MAG_4th_diff = fourth_difference(MAGCOM) # 4th difference values. Discrete. Non-normalized. Was originally calculated using #np.diff(MAGCOM, n=4)
        gdb.loc[line, "MAGCOM_2nd"] = np.pad(np.diff(MAGCOM, n=2), (0, 2), constant_values=np.nan) # save 2nd difference to gdb
        gdb.loc[line, "MAGCOM_4th"] = MAG_4th_diff # save 4th difference to gdb
        # Identify if there is OOS 4th difference on this line:
        OOS_4th_mask = (np.abs(MAG_4th_diff) > MAG_4th_diff_OOS_threshold) # Where 4th diff noise out-of-spec mask. 
        OOS_4th = sum ( OOS_4th_mask) # Number of data points for which 4th difference noise out-of-spec.
        gdb.loc[line, "mag_4th_diff_OOS"] = OOS_4th_mask.astype('int8') # Write the OOS mask to gdb
        if OOS_4th>0: # If any out of spec records.
            OOS_4th_line_count += 1 # add a line to the count!
            noise_summary.loc[len(noise_summary)] = [flight_num, line, OOS_4th] # Append the line to the noise_summary.

    data.data = gdb
    return data
    
    # return (gdb,
    #         OOS_4th_line_count,
    #         noise_summary,
    #         OOS_diurnal_line_count,
    #         diurnal_summary,
    #         drape_summary
    #         )
