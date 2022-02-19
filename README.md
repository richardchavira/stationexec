# stationexec installation
Note:  conflict with arrow library
install arrow 0.17.0 first

pip install arrow==0.17.0



First:
download and install stationexec

pip install stationexec-1.1.0-py2.py3-none-any.whl

Note: this will install several helper scripts...
se-hello
se-launch
se-station
se-tool
se-setup

if they do not run add the script location to your path.
(easy way to see where they were installed is to try to uninstall stationexec  -- pip uninstall stationexec    it will ask if you are sure and display the location)

run se-setup after install

this will create stationexec folder

(linux/mac) ~/stationexec
(windows) c:\stationexec

If this is good you can test your installation by running
se-hello

This will launch the example station.
