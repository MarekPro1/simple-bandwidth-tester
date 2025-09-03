# Simple Bandwidth Tester

A minimalist SSH-based bandwidth testing tool for Windows computers using iperf3.

## Features

- Tests bandwidth between Windows computers via SSH
- Bidirectional testing (upload and download speeds)
- Simple JSON configuration
- Clear results in Mbps

## Requirements

- Python 3.6+
- `paramiko` library for SSH connections
- `iperf3` installed on target computers (C:\iperf3\iperf3.19.1_64\iperf3.exe)

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/simple-bandwidth-tester.git
cd simple-bandwidth-tester
```

2. Install Python dependencies:
```bash
pip install paramiko
```

3. Install iperf3 on all Windows computers:
   - Download from: https://github.com/ar51an/iperf3-win-builds/releases
   - Extract to `C:\iperf3\`

## Configuration

Edit `network_config.json` to add your devices:

```json
{
  "devices": [
    {
      "name": "Computer1",
      "ip": "192.168.1.10",
      "type": "computer",
      "location": "Office",
      "link_speed": "1Gbps"
    },
    {
      "name": "Computer2",
      "ip": "192.168.1.11",
      "type": "computer",
      "location": "Server Room",
      "link_speed": "10Gbps"
    }
  ]
}
```

## Usage

Run the bandwidth test:

```bash
python simple_bandwidth_test.py
```

## Output Example

```
============================================================
BANDWIDTH TEST RESULTS
============================================================
Computer1->Computer2      :  2296.00 Mbps [OK]
Computer2->Computer1      :  2361.00 Mbps [OK]
============================================================
```

## SSH Credentials

Currently hardcoded in the script:
- Username: `admin`
- Password: `Milostvns123!`

To change, edit lines 12-13 in `simple_bandwidth_test.py`.

## License

MIT

## Author

Created for simple network bandwidth testing between Windows computers.