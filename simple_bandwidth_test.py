#!/usr/bin/env python3
"""
Simple Bandwidth Test Tool
Only measures bandwidth between computers via SSH
"""

import paramiko
import json
import time
import sys
import argparse
import os

# Color codes for Windows terminal
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    
# Enable colors on Windows
if sys.platform == 'win32':
    os.system('color')

class SimpleBandwidthTester:
    def __init__(self, username, password, config_file="network_config.json"):
        self.username = username
        self.password = password
        self.config_file = config_file
        self.computers = []
        self.load_config()
        
    def load_config(self):
        """Load only computers from config"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                # Only load computers, ignore switches for now
                self.computers = [d for d in config['devices'] if d['type'] == 'computer']
                print(f"\n{Colors.CYAN}{'='*60}")
                print(f"  NETWORK DEVICES FOUND")
                print(f"{'='*60}{Colors.END}")
                print(f"{Colors.WHITE}Found {Colors.BOLD}{len(self.computers)}{Colors.END} {Colors.WHITE}computers to test:{Colors.END}\n")
                for comp in self.computers:
                    link_speed = comp.get('link_speed', 'Unknown')
                    location = comp.get('location', 'Unknown')
                    print(f"  {Colors.GREEN}>{Colors.END} {Colors.BOLD}{comp['name']:<15}{Colors.END} {Colors.GRAY}({comp['ip']:<15}){Colors.END} - {Colors.CYAN}{link_speed:<7}{Colors.END} @ {Colors.YELLOW}{location}{Colors.END}")
        except Exception as e:
            print(f"{Colors.RED}Error loading config: {e}{Colors.END}")
            sys.exit(1)
            
    def ssh_connect(self, ip):
        """Create SSH connection"""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(ip, username=self.username, password=self.password, timeout=10)
            return ssh
        except Exception as e:
            print(f"  Failed to connect to {ip}: {e}")
            return None
            
    def check_and_install_iperf(self, ssh, computer_name):
        """Check if iperf3 is installed and install it if not"""
        # Check common iperf3 locations
        iperf_locations = [
            r'C:\iperf3\iperf3.19.1_64\iperf3.exe',
            r'C:\iperf3\iperf3.exe',
            r'C:\Program Files\iperf3\iperf3.exe'
        ]
        
        for path in iperf_locations:
            stdin, stdout, stderr = ssh.exec_command(f'if exist "{path}" echo FOUND:{path}')
            result = stdout.read().decode().strip()
            if result.startswith("FOUND:"):
                return path
        
        # iperf3 not found, attempt to install it
        print(f"  iperf3 not found on {computer_name}, attempting to install...")
        
        # Create iperf3 directory
        ssh.exec_command('mkdir C:\\iperf3 2>nul')
        time.sleep(1)
        
        # First, let's check what we can do on this system
        print(f"  Checking system capabilities on {computer_name}...")
        
        # Test if PowerShell works
        stdin, stdout, stderr = ssh.exec_command('powershell -Command "Write-Host TEST"')
        test_output = stdout.read().decode().strip()
        if "TEST" not in test_output:
            print(f"  PowerShell test failed. Output: {test_output}")
            # Try alternative: copy from another computer if available
            print(f"  Attempting alternative installation method...")
            
            # Try using curl or certutil (built into Windows)
            download_cmd = 'certutil -urlcache -f https://github.com/ar51an/iperf3-win-builds/releases/download/3.19.1/iperf3.19.1-win64.zip C:\\iperf3\\iperf3.zip'
            print(f"  Downloading using certutil...")
            stdin, stdout, stderr = ssh.exec_command(download_cmd, timeout=120)
            output = stdout.read().decode()
            errors = stderr.read().decode()
            
            if "completed successfully" in output.lower():
                # Extract using PowerShell or tar (Windows 10+ has tar)
                extract_cmd = 'powershell -Command "Expand-Archive -Path C:\\iperf3\\iperf3.zip -DestinationPath C:\\iperf3\\ -Force"'
                stdin, stdout, stderr = ssh.exec_command(extract_cmd)
                print(f"  Extraction attempted")
            else:
                print(f"  Download failed: {errors}")
                return None
        else:
            # PowerShell works, use the original method with better error reporting
            download_cmd = '''powershell -ExecutionPolicy Bypass -Command "
            try {
                [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
                $url = 'https://github.com/ar51an/iperf3-win-builds/releases/download/3.19.1/iperf3.19.1-win64.zip'
                $output = 'C:\\iperf3\\iperf3.zip'
                Write-Host 'Downloading iperf3...'
                Invoke-WebRequest -Uri $url -OutFile $output -UseBasicParsing
                Write-Host 'Extracting iperf3...'
                Expand-Archive -Path $output -DestinationPath C:\\iperf3\\ -Force
                Write-Host 'Installation complete'
            } catch {
                Write-Host 'Error: ' $_.Exception.Message
                exit 1
            }
            "'''
            
            print(f"  Downloading iperf3 for {computer_name}...")
            stdin, stdout, stderr = ssh.exec_command(download_cmd, timeout=120)
            output = stdout.read().decode()
            errors = stderr.read().decode()
            
            print(f"  Download output: {output}")
            if errors:
                print(f"  Installation errors: {errors}")
        
        # Check if installation was successful
        iperf_path = r'C:\iperf3\iperf3.19.1_64\iperf3.exe'
        stdin, stdout, stderr = ssh.exec_command(f'if exist "{iperf_path}" echo SUCCESS')
        if "SUCCESS" in stdout.read().decode():
            print(f"  iperf3 successfully installed on {computer_name}")
            return iperf_path
        else:
            print(f"  Failed to install iperf3 on {computer_name}")
            return None
    
    def start_iperf_server(self, server_ip, server_name):
        """Start iperf3 server on a computer"""
        print(f"\nStarting iperf3 server on {server_name} ({server_ip})...")
        
        ssh = self.ssh_connect(server_ip)
        if not ssh:
            return False
            
        try:
            # Kill any existing iperf3 processes
            ssh.exec_command("taskkill /F /IM iperf3.exe 2>nul")
            time.sleep(1)
            
            # Check and install iperf3 if needed
            iperf_path = self.check_and_install_iperf(ssh, server_name)
            if not iperf_path:
                ssh.close()
                return False
                
            # Start iperf3 server in background using PowerShell
            ps_cmd = f'powershell -Command "Start-Process -FilePath \\"{iperf_path}\\" -ArgumentList \\"-s -p 5201\\" -WindowStyle Hidden"'
            ssh.exec_command(ps_cmd)
            time.sleep(3)
            
            # Verify server is running
            stdin, stdout, stderr = ssh.exec_command('netstat -an | findstr :5201')
            if "5201" in stdout.read().decode():
                print(f"  iperf3 server started successfully on {server_name}")
                ssh.close()
                return True
            else:
                print(f"  Failed to start iperf3 server on {server_name}")
                ssh.close()
                return False
                
        except Exception as e:
            print(f"  Error: {e}")
            ssh.close()
            return False
            
    def run_iperf_client(self, client_ip, client_name, server_ip, server_name):
        """Run iperf3 client test from one computer to another"""
        print(f"Running bandwidth test: {client_name} -> {server_name}...")
        
        ssh = self.ssh_connect(client_ip)
        if not ssh:
            return None
            
        try:
            # Check and install iperf3 if needed
            iperf_path = self.check_and_install_iperf(ssh, client_name)
            if not iperf_path:
                ssh.close()
                return None
                
            # Run iperf3 client test
            cmd = f'"{iperf_path}" -c {server_ip} -t 10 -f m'  # 10 second test, output in Mbps
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=20)
            
            output = stdout.read().decode()
            errors = stderr.read().decode()
            
            if "Connection refused" in errors or "Connection refused" in output:
                print(f"  ERROR: Cannot connect to iperf3 server on {server_name}")
                ssh.close()
                return None
                
            # Parse bandwidth from output
            # Look for lines like: "[  4]   0.00-10.00  sec  1.09 GBytes   938 Mbits/sec"
            bandwidth_mbps = None
            lines = output.split('\n')
            for line in lines:
                if 'sender' in line.lower() or 'receiver' in line.lower():
                    continue  # Skip summary lines
                if 'bits/sec' in line:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if 'bits/sec' in part:
                            # Previous part should be the number
                            if i > 0:
                                value = parts[i-1]
                                try:
                                    bandwidth_mbps = float(value)
                                    # Check if it's in Gbits/sec
                                    if 'Gbits/sec' in part:
                                        bandwidth_mbps *= 1000
                                    elif 'Kbits/sec' in part:
                                        bandwidth_mbps /= 1000
                                    break
                                except:
                                    pass
                                    
            ssh.close()
            
            if bandwidth_mbps:
                print(f"  Result: {bandwidth_mbps:.2f} Mbps")
                return bandwidth_mbps
            else:
                print(f"  ERROR: Could not parse bandwidth from output")
                return None
                
        except Exception as e:
            print(f"  Error: {e}")
            ssh.close()
            return None
            
    def get_link_speed(self, comp_name):
        """Get the link speed in Mbps from computer config"""
        for comp in self.computers:
            if comp['name'] == comp_name:
                speed_str = comp.get('link_speed', '1Gbps')
                # Convert to Mbps
                if 'Gbps' in speed_str:
                    return float(speed_str.replace('Gbps', '')) * 1000
                elif 'Mbps' in speed_str:
                    return float(speed_str.replace('Mbps', ''))
        return 1000  # Default to 1Gbps
    
    def test_computer_pair(self, comp1, comp2):
        """Test bandwidth between two computers"""
        print(f"\n{Colors.BLUE}{'-'*60}")
        print(f"  {Colors.BOLD}Testing: {comp1['name']} <-> {comp2['name']}{Colors.END}")
        print(f"{Colors.BLUE}{'-'*60}{Colors.END}")
        
        # Show link speeds
        speed1 = self.get_link_speed(comp1['name'])
        speed2 = self.get_link_speed(comp2['name'])
        max_theoretical = min(speed1, speed2)
        
        print(f"  {Colors.GRAY}Link speeds: {comp1['name']}={comp1.get('link_speed', 'Unknown')}, {comp2['name']}={comp2.get('link_speed', 'Unknown')}")
        print(f"  Theoretical maximum: {max_theoretical:.0f} Mbps{Colors.END}\n")
        
        results = {}
        
        # Test comp1 -> comp2
        if self.start_iperf_server(comp2['ip'], comp2['name']):
            time.sleep(2)
            bandwidth = self.run_iperf_client(comp1['ip'], comp1['name'], 
                                             comp2['ip'], comp2['name'])
            if bandwidth:
                key = f"{comp1['name']}->{comp2['name']}"
                results[key] = {
                    'bandwidth': bandwidth,
                    'max_speed': max_theoretical,
                    'utilization': (bandwidth / max_theoretical) * 100
                }
        
        # Test comp2 -> comp1 (reverse direction)
        if self.start_iperf_server(comp1['ip'], comp1['name']):
            time.sleep(2)
            bandwidth = self.run_iperf_client(comp2['ip'], comp2['name'],
                                             comp1['ip'], comp1['name'])
            if bandwidth:
                key = f"{comp2['name']}->{comp1['name']}"
                results[key] = {
                    'bandwidth': bandwidth,
                    'max_speed': max_theoretical,
                    'utilization': (bandwidth / max_theoretical) * 100
                }
                
        return results
        
    def run_all_tests(self):
        """Test bandwidth between all computer pairs"""
        if len(self.computers) < 2:
            print(f"{Colors.RED}Need at least 2 computers to run bandwidth tests{Colors.END}")
            return
            
        print(f"\n{Colors.HEADER}{'='*60}")
        print(f"  {Colors.BOLD}BANDWIDTH TESTING STARTED{Colors.END}")
        print(f"{Colors.HEADER}{'='*60}{Colors.END}")
        
        all_results = {}
        
        # Test each pair of computers
        for i in range(len(self.computers)):
            for j in range(i+1, len(self.computers)):
                results = self.test_computer_pair(self.computers[i], self.computers[j])
                all_results.update(results)
                
        # Display final results
        print(f"\n{Colors.CYAN}{'='*80}")
        print(f"  {Colors.BOLD}FINAL TEST RESULTS{Colors.END}")
        print(f"{Colors.CYAN}{'='*80}{Colors.END}\n")
        
        if all_results:
            # Print header
            print(f"  {Colors.BOLD}{'Connection':<30} {'Bandwidth':<12} {'NIC Rate':<10} {'Utilization':<12} Status{Colors.END}")
            print(f"  {Colors.GRAY}{'-'*78}{Colors.END}")
            
            for connection, data in all_results.items():
                bandwidth = data['bandwidth']
                max_speed = data['max_speed']
                utilization = data['utilization']
                
                # Determine status and color based on utilization
                if utilization >= 90:
                    status_color = Colors.GREEN
                    status_text = "EXCELLENT"
                elif utilization >= 70:
                    status_color = Colors.YELLOW
                    status_text = "GOOD"
                elif utilization >= 50:
                    status_color = Colors.YELLOW
                    status_text = "FAIR"
                else:
                    status_color = Colors.RED
                    status_text = "POOR"
                
                # Format bandwidth display
                bandwidth_str = f"{bandwidth:,.0f} Mbps"
                max_speed_str = f"{max_speed:,.0f} Mbps"
                utilization_str = f"{utilization:.1f}%"
                
                # Create utilization bar using ASCII characters
                bar_length = 20
                filled = int(utilization * bar_length / 100)
                bar = '#' * filled + '-' * (bar_length - filled)
                
                print(f"  {Colors.WHITE}{connection:<30}{Colors.END} "
                      f"{Colors.BOLD}{bandwidth_str:<12}{Colors.END} "
                      f"{Colors.GRAY}{max_speed_str:<10}{Colors.END} "
                      f"{utilization_str:<12} "
                      f"{status_color}[{bar}] {status_text}{Colors.END}")
        else:
            print(f"  {Colors.RED}No successful tests completed{Colors.END}")
            
        print(f"\n{Colors.CYAN}{'='*80}{Colors.END}")
        
        # Print legend
        print(f"\n  {Colors.GRAY}Legend:{Colors.END}")
        print(f"    {Colors.GREEN}#{Colors.END} EXCELLENT (90-100%)  "
              f"{Colors.YELLOW}#{Colors.END} GOOD (70-89%)  "
              f"{Colors.YELLOW}#{Colors.END} FAIR (50-69%)  "
              f"{Colors.RED}#{Colors.END} POOR (<50%){Colors.END}")

def main():
    parser = argparse.ArgumentParser(description='Simple Bandwidth Test Tool')
    parser.add_argument('-u', '--username', required=True, help='SSH username')
    parser.add_argument('-p', '--password', required=True, help='SSH password')
    parser.add_argument('-c', '--config', default='network_config.json', help='Config file (default: network_config.json)')
    
    args = parser.parse_args()
    
    tester = SimpleBandwidthTester(args.username, args.password, args.config)
    tester.run_all_tests()

if __name__ == "__main__":
    main()