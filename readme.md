# Gragps view - tool for displaying data from the serial port as graphs (Windows, Linux,...)

## Purpose of the application:

The application reads data from the COM port, parses each line as a set of floats separated by spaces/tabs, 
and then displays the data on graphs.
The timestamp used is the moment when the data is read from the port."

## How to install
* `python3 -m virtualenv venv`
* `./venv/bin/pip install -r requirements.txt`

## How to run

`./venv/bin/python graphs_view.py`
or in linux you can use: `./graphs_view.sh`