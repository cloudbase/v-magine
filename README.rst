# Some quick info to get the hacking started

git clone https://github.com/openstack/python-glanceclient
cd python-glanceclient
git fetch https://review.openstack.org/openstack/python-glanceclient refs/changes/16/137916/1 && git checkout -b bug/1397554 FETCH_HEAD
python setup.py install
cd ..

git clone https://github.com/openstack/python-keystoneclient
cd python-keystoneclient
git fetch https://review.openstack.org/openstack/python-keystoneclient refs/changes/15/137915/1 && git checkout -b bug/1397554 FETCH_HEAD
python setup.py install
cd ..

git clone https://github.com/cloudbase/pyinstaller.git
cd pyinstaller
python setup.py install
cd ..

git clone https://github.com/cloudbase/pybootd.git
cd pybootd
python setup.py install
cd ..

# Download and install
http://downloads.sourceforge.net/project/pywin32/pywin32/Build%20219/pywin32-219.win32-py2.7.exe?r=http%3A%2F%2Fsourceforge.net%2Fprojects%2Fpywin32%2Ffiles%2Fpywin32%2FBuild%2520219%2F&ts=1417467131&use_mirror=heanet
# and
http://sourceforge.net/projects/pyqt/files/PyQt4/PyQt-4.11.3/PyQt4-4.11.3-gpl-Py2.7-Qt4.8.6-x32.exe
# and
http://www.voidspace.org.uk/downloads/pycrypto26/pycrypto-2.6.win32-py2.7.exe

# In the v-magine / stackinabox dir:
pip install -r requirements.txt

# Build project
.\buildpackage.cmd

#You'll find the built binaries in the "dist" dir
