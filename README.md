# hostchecker
Simple tool for checking availability and latency of web services.  
It has been designed for checking EEP-sites in I2P network, so connection goes through local proxy by default; but, with some remarks, it can be used to check normal sites too.

## Info
hostchecker requires a filename as an argument (say, *hosts.txt*). This file (*hosts.txt*) must contain hostnames (i.e. *example.org*), one hostname on each line.

Along with output to the terminal, hostchecker will write to SQLite database file, named **hosts.db** (it'll be created if not exists), located in current working directory.  
You can generate HTML report with hosts table, using [htmlreport](https://github.com/h5vx/htmlreport)

### hosts.db fields
hosts.db contains single table named **hosts** with following fields:
* **hostname**
* **type** — may be **UP**, **DOWN** or **ERROR**
* **reason** — specified when type is **DOWN** or **ERROR**
	* When type is **ERROR**, contains representation of Python's exception object
	* When type is **DOWN**, contains **TIMEOUT** or **DOWN (code)**
		* **TIMEOUT** says that connection timed out, and **latency** field will be set to timeout value (specified by `--timeout`, 60 by default)
		* **DOWN (code)** says that HTTP server respond with an error, e.g. DOWN (500). Yes, that doesn't mean that host is down, but when using with I2P (which is main goal of the tool), I2P local proxy may respond HTTP 500 when host is down
* **latency** — response latency in seconds. When **type** is **ERROR**, it will be set to `-1.0`
* **added** — date when entry added to datebase; this field will never change it's value
* **updated** — date when entry was updated

hosts.db will never contain `NULL` values, as some SQLite drivers doesn't accept that (e.g. `go-sqlite3` for Go). Instead, empty fields will contain zero-values of it's type (0 for NUMERIC, "" for TEXT, etc)

## Usage
See `./hostchecker -h` for help
* **-t**, **--threads** — number of HTTP request threads *(5 by default)*
* **-n**, **--timeout** — how many time to wait response before give up, seconds *(60 by default)*
* **-p**, **--proxy** — HTTP proxy address, may be without leading `http://` *(http://127.0.0.1:4444 by default)*
* **-np**, **--no-proxy** — not use proxy (however, `requests` module may grab and use proxy from environment variable `http_proxy`, when it's set!)

## Requirements
* Python 3
* requests
