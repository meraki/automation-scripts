# Meraki Secure Connect Remote Access Logs Analyzer

This script fetches and analyzes Meraki Secure Connect remote access logs from the Meraki API and generates statistics for selected columns. The results are displayed in a color-coded table, and the data can be saved to a CSV file.

## Requirements

- Python 3.6+
- `pandas` library
- `termcolor` library
- `requests` library

Install required libraries using the following command:

```bash
pip3 install pandas termcolor requests
```

## Usage

Run the script from the command line:

```bash
python3 remoteAccessLogsAnalyzer.py
```

You will be prompted to enter your Meraki organization ID, API key, and the desired date range (in epoch time).

The script will fetch remote access logs from the Meraki API, parse them, and generate a DataFrame with the following columns:

- Timestamp
- Connect Timestamp
- Connection Event
- OS Version
- AnyConnect Version
- Internal IP
- External IP

The Connection Event and OS Version columns are color-coded for better readability. "connected" values are displayed in green, while "disconnected" values are displayed in red. Windows OS versions are displayed in yellow, and other OS versions are displayed in blue.

The script will also generate statistics for the following columns:

- OS Version
- AnyConnect Version
- Connection Event
- Internal IP

The generated data can be saved to a CSV file with the creation date in the file name.

## Maintainers & Contributors

[Yossi Meloch](mailto:ymeloch@cisco.com)

## Acknowledgements

- [Cisco Meraki](https://www.meraki.com/) for providing a robust and easy-to-use API

Please note that this script is provided "as is" without warranty of any kind, either expressed or implied, including limitation warranties of merchantability, fitness for a particular purpose, and noninfringement. Use at your own risk.
