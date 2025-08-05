# OM_DGGS_python_extensions
Oasis montaj DGGS python extensions

Date: 2025-06-11
Author: Eric Petersen

How-to:

1) Copy python scripts from here to:
C:\Users\\$USERNAME$\Documents\Geosoft\Desktop Applications\python\

2) Copy omn files from here to:
C:\Users\\$USERNAME$\Documents\Geosoft\Desktop Applications\omn\

3) In Oasis montaj, go to menu: Project > Manage Menus. In the window that pops up, scroll
to the bottom where it has "User Menus" and select "DGGS." Click OK. The menus will reload
and you should now have the "DGGS" menu on your menu bar, and when you click on it you will
see the python extensions appear in the drop-down menu.

NOTE: GX Developer will need to be installed on your machine/Oasis montaj instance of python.
To do this, open a command prompt window (Anaconda Prompt works well) and type "pip install geosoft".
If you encounter admin privilege errors, one possible solution is to run command prompt as
administrator and use the command "python -m pip install geosoft".


Detailed descriptions of the function of various extensions are given in comment headings
within the python files.

Copyright (C) 2025 Eric Petersen
These programs are free software: you can redistribute them and/or modify them under the terms of the 
GNU General Public License as published by the Free Software Foundation, either version 3 of the 
License, or (at your option) any later version. These programs are distributed in the hope that they 
will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY 
or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details, 
<http://www.gnu.org/licenses/>.