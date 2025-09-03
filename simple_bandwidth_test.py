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
    def __init__(self, username, password, config_file="network_config.json", verbose=False):
        self.username = username
        self.password = password
        self.config_file = config_file
        self.verbose = verbose
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
            if self.verbose:
                print(f"  {Colors.GRAY}[DEBUG] Connecting to {ip}...{Colors.END}")
            ssh.connect(ip, username=self.username, password=self.password, timeout=10)
            if self.verbose:
                print(f"  {Colors.GREEN}[DEBUG] Connected successfully to {ip}{Colors.END}")
            return ssh
        except Exception as e:
            if self.verbose:
                print(f"  {Colors.RED}[DEBUG] Failed to connect to {ip}: {e}{Colors.END}")
            else:
                print(f"  {Colors.RED}Failed to connect to {ip}{Colors.END}")
            return None
            
    def verify_iperf_server(self, server_ip):
        """Just verify that iperf3 server is running"""
        ssh = self.ssh_connect(server_ip)
        if not ssh:
            return False
            
        try:
            # Check if server is listening on port 5201
            stdin, stdout, stderr = ssh.exec_command('netstat -an | findstr :5201')
            netstat_output = stdout.read().decode()
            ssh.close()
            
            is_listening = "5201" in netstat_output and "LISTENING" in netstat_output
            
            if self.verbose:
                if is_listening:
                    print(f"  {Colors.GREEN}[DEBUG] iperf3 server is running on {server_ip}{Colors.END}")
                else:
                    print(f"  {Colors.RED}[DEBUG] iperf3 server NOT running on {server_ip}{Colors.END}")
                    print(f"  {Colors.GRAY}[DEBUG] Netstat output: {netstat_output if netstat_output else 'No output'}{Colors.END}")
            
            return is_listening
                
        except Exception as e:
            if self.verbose:
                print(f"  {Colors.RED}[DEBUG] Error checking server on {server_ip}: {e}{Colors.END}")
            ssh.close()
            return False
            
    def run_iperf_client(self, client_ip, client_name, server_ip, server_name):
        """Run iperf3 client test from one computer to another"""
        ssh = self.ssh_connect(client_ip)
        if not ssh:
            return None
            
        try:
            # Assume iperf3 is installed
            iperf_path = r'C:\iperf3\iperf3.19.1_64\iperf3.exe'
            
            if self.verbose:
                print(f"  {Colors.GRAY}[DEBUG] Running test: {client_name} -> {server_name}{Colors.END}")
                
            # Run iperf3 client test
            cmd = f'"{iperf_path}" -c {server_ip} -t 10 -f m'  # 10 second test, output in Mbps
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=20)
            
            output = stdout.read().decode()
            errors = stderr.read().decode()
            
            if self.verbose and errors:
                print(f"  {Colors.GRAY}[DEBUG] iperf3 stderr: {errors}{Colors.END}")
            
            if "Connection refused" in errors or "Connection refused" in output:
                if self.verbose:
                    print(f"  {Colors.RED}[DEBUG] Cannot connect to iperf3 server on {server_name} ({server_ip}){Colors.END}")
                else:
                    print(f"  {Colors.RED}Cannot connect to {server_name}{Colors.END}")
                ssh.close()
                return None
                
            # Parse bandwidth from output
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
            
            if self.verbose:
                if bandwidth_mbps:
                    print(f"  {Colors.GREEN}[DEBUG] Test result: {bandwidth_mbps:.2f} Mbps{Colors.END}")
                else:
                    print(f"  {Colors.RED}[DEBUG] Could not parse bandwidth from output{Colors.END}")
                    print(f"  {Colors.GRAY}[DEBUG] Output: {output[:500]}{Colors.END}")
            
            return bandwidth_mbps
                
        except Exception as e:
            if self.verbose:
                print(f"  {Colors.RED}[DEBUG] Error running client: {e}{Colors.END}")
            ssh.close()
            return None
            
    def print_result(self, connection, bandwidth, max_speed):
        """Print a single test result in one line"""
        utilization = (bandwidth / max_speed) * 100
        
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
        
        # Format strings
        bandwidth_str = f"{bandwidth:,.0f} Mbps"
        max_speed_str = f"{max_speed:,.0f} Mbps"
        utilization_str = f"{utilization:.1f}%"
        
        # Create utilization bar
        bar_length = 20
        filled = int(utilization * bar_length / 100)
        bar = '#' * filled + '-' * (bar_length - filled)
        
        print(f"  {Colors.WHITE}{connection:<30}{Colors.END} "
              f"{Colors.BOLD}{bandwidth_str:<12}{Colors.END} "
              f"{Colors.GRAY}{max_speed_str:<10}{Colors.END} "
              f"{utilization_str:<12} "
              f"{status_color}[{bar}] {status_text}{Colors.END}")
    
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
    
    def run_all_tests(self):
        """Test bandwidth between all computer pairs"""
        if len(self.computers) < 2:
            print(f"{Colors.RED}Need at least 2 computers to run bandwidth tests{Colors.END}")
            return
            
        print(f"\n{Colors.CYAN}{'='*80}")
        print(f"  {Colors.BOLD}BANDWIDTH TEST RESULTS{Colors.END}")
        print(f"{Colors.CYAN}{'='*80}{Colors.END}\n")
        
        # Print header
        print(f"  {Colors.BOLD}{'Connection':<30} {'Bandwidth':<12} {'NIC Rate':<10} {'Utilization':<12} Status{Colors.END}")
        print(f"  {Colors.GRAY}{'-'*78}{Colors.END}")
        
        all_results = {}
        
        # Test each pair of computers and display results immediately
        for i in range(len(self.computers)):
            for j in range(i+1, len(self.computers)):
                comp1 = self.computers[i]
                comp2 = self.computers[j]
                
                # Get link speeds
                speed1 = self.get_link_speed(comp1['name'])
                speed2 = self.get_link_speed(comp2['name'])
                max_theoretical = min(speed1, speed2)
                
                # Test comp1 -> comp2
                if self.verify_iperf_server(comp2['ip']):
                    bandwidth = self.run_iperf_client(comp1['ip'], comp1['name'], 
                                                     comp2['ip'], comp2['name'])
                    if bandwidth:
                        self.print_result(f"{comp1['name']}->{comp2['name']}", 
                                        bandwidth, max_theoretical)
                elif self.verbose:
                    print(f"  {Colors.YELLOW}[DEBUG] Skipping {comp1['name']}->{comp2['name']} (no server){Colors.END}")
                
                # Test comp2 -> comp1 
                if self.verify_iperf_server(comp1['ip']):
                    bandwidth = self.run_iperf_client(comp2['ip'], comp2['name'],
                                                     comp1['ip'], comp1['name'])
                    if bandwidth:
                        self.print_result(f"{comp2['name']}->{comp1['name']}", 
                                        bandwidth, max_theoretical)
                elif self.verbose:
                    print(f"  {Colors.YELLOW}[DEBUG] Skipping {comp2['name']}->{comp1['name']} (no server){Colors.END}")
                
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
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose debug output')
    
    args = parser.parse_args()
    
    tester = SimpleBandwidthTester(args.username, args.password, args.config, args.verbose)
    tester.run_all_tests()

if __name__ == "__main__":
    main()