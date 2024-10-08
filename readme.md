# Graphs view - tool for displaying data from the Serial-Port/UDP/TCP as graphs (Windows, Linux,...)

## Purpose of the application:

The application reads data from the COM port, parses each line as a set of floats separated by spaces/tabs, 
and then displays the data on graphs.
The timestamp used is the moment when the data is read from the port."

## How to install:
1. You need to [install the virtualenv module](https://virtualenv.pypa.io/en/latest/installation.html) in your Python3 environment before proceeding to the next steps.
2. Creating virtual env: `python3 -m virtualenv venv`
3. Installing module:
    * Linux: `./venv/bin/pip install -e .`
    * Windows: `venv\Scripts\pip install -e .`

## How to run:
* Linux: `./venv/bin/graphs_view`
* Windows: `venv\Scripts\graphs_view`
