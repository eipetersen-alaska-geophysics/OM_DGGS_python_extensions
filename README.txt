DGGS python extensions

Date: 2025-06-11
Author: Eric Petersen

How-to:

1) Copy python scripts from 
\\morta.dnr.state.ak.us\geophysics\projects\magnetic_qc_working\python_extensions\python\
to:
C:\Users\$USERNAME$\Documents\Geosoft\Desktop Applications\python\

2) Copy omn files from
\\morta.dnr.state.ak.us\geophysics\projects\magnetic_qc_working\python_extensions\omn\
to:
C:\Users\$USERNAME$\Documents\Geosoft\Desktop Applications\omn\

3) In Oasis montaj, go to menu: Project > Manage Menus. In the window that pops up, scroll
to the bottom where it has "User Menus" and select "DGGS." Click OK. The menus will reload
and you should now have the "DGGS" menu on your menu bar, and when you click on it you will
see the python extensions appear in the drop-down menu.

NOTE: GX Developer will need to be installed on your machine/Oasis montaj instance of python.
To do this, open a command prompt window (Anaconda Prompt works well) and type "pip install geosoft".
If you encounter admin privilege errors, one possible solution is to run command prompt as
administrator and use the command "python -m pip install geosoft".
